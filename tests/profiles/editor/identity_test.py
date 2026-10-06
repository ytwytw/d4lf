"""Editor rows keep canonical identities when localized labels collide (zhCN 巨人贡品 / 毒素伤害 / 暗影伤害)."""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QListWidgetItem, QWidget

from src.game_data import GameCatalog
from src.game_data import catalog as catalog_module
from src.profiles import AffixFilterModel, CharmFilterModel, ProfileDocumentStore, SealFilterModel, TributeFilterModel
from src.profiles.affix.widget import AffixWidget
from src.profiles.editor.identity import (
    IDENTITY_ROLE,
    current_identity,
    identity_for_text,
    item_identity,
    populate_identities,
    select_identity,
)
from src.profiles.tribute import CreateTribute, RemoveTribute, TributesTab

SHARED_AFFIXES = {"毒素伤害": ("poison_damage", "poisoning_damage"), "暗影伤害": ("shade_damage", "shadow_damage")}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def zh(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", catalog)
    return catalog


def _rows(combo) -> dict[str, str]:
    return {combo.itemData(row): combo.itemText(row) for row in range(combo.count())}


def test_identity_helpers_store_and_resolve_row_data(qapp) -> None:
    combo = QComboBox()
    combo.setEditable(True)
    populate_identities(combo, {"b": "同名（b）", "a": "同名（a）"})
    assert [combo.itemText(row) for row in range(combo.count())] == ["同名（a）", "同名（b）"]
    assert select_identity(combo, "b")
    assert current_identity(combo) == "b"
    assert not select_identity(combo, "missing")
    assert identity_for_text(combo, "同名（a）") == "a"
    assert identity_for_text(combo, "同名") is None
    item = QListWidgetItem("row")
    assert item_identity(item) is None
    item.setData(IDENTITY_ROLE, "a")
    assert item_identity(item) == "a"


def test_create_tribute_reaches_every_identity_and_rejects_ambiguous_text(zh, qapp) -> None:
    dialog = CreateTribute([])
    assert set(_rows(dialog.name_input)) == set(zh.tribute_dict)
    for canonical in ("tribute_of_heritage", "tribute_of_titans"):
        dialog.name_input.setCurrentIndex(dialog.name_input.findData(canonical))
        assert dialog.get_value().name == [canonical]
    dialog.name_input.setCurrentText("巨人贡品")
    with pytest.raises(ValueError, match="valid tribute"):
        dialog.get_value()


@pytest.mark.parametrize("removed", ["tribute_of_heritage", "tribute_of_titans"])
def test_tribute_tab_removes_exactly_the_selected_identity(zh, qapp, removed) -> None:
    tributes = TributeFilterModel(name=["tribute_of_heritage", "tribute_of_titans"], rarities=[])
    tab = TributesTab(tributes)
    tab.load()
    items = [tab.list_widget.item(row) for row in range(tab.list_widget.count())]
    assert len({item.text() for item in items if item is not None}) == 2
    selected = items[tributes.name.index(removed)]
    assert selected is not None
    selected.setSelected(True)
    tab.remove_selected()
    assert tributes.name == [name for name in ("tribute_of_heritage", "tribute_of_titans") if name != removed]


def test_remove_tribute_dialog_returns_identities(zh, qapp) -> None:
    dialog = RemoveTribute(["tribute_of_heritage", "tribute_of_titans"])
    dialog.checkbox_list[0].setChecked(True)
    assert dialog.get_value() == ["tribute_of_heritage"]


@pytest.mark.parametrize("canonical", [name for pair in SHARED_AFFIXES.values() for name in pair])
def test_every_shared_affix_identity_is_selectable(zh, qapp, canonical) -> None:
    widget = AffixWidget(AffixFilterModel(name="maximum_life"))
    widget.name_combo.setCurrentIndex(widget.name_combo.findData(canonical))
    assert widget.affix.name == canonical


@pytest.mark.parametrize("canonical", [name for pair in SHARED_AFFIXES.values() for name in pair])
def test_existing_shared_affix_survives_display_and_reselection(zh, qapp, canonical) -> None:
    affix = AffixFilterModel(name=canonical)
    widget = AffixWidget(affix)
    assert widget.name_combo.currentData() == canonical
    widget.update_name(widget.name_combo.currentText())
    widget.name_combo.setCurrentIndex(widget.name_combo.findData(canonical))
    assert affix.name == canonical
    widget.update_name(next(label for label in SHARED_AFFIXES if label in widget.name_combo.currentText()))
    assert not affix.name  # the bare shared label is ambiguous and never guessed


class _ConfigParent(QWidget):
    def __init__(self, config: object) -> None:
        super().__init__()
        self.config = config


def _parented(config: object) -> QWidget:
    return _ConfigParent(config)


@pytest.mark.parametrize("kind", ["seal", "charm"])
def test_seal_and_charm_paths_keep_identity_for_colliding_labels(zh, qapp, monkeypatch, kind) -> None:
    shared = {"seal_x_alpha": "同名词缀", "seal_x_beta": "同名词缀"}
    if kind == "seal":
        monkeypatch.setattr(zh, "seal_affix_dict", {**zh.seal_affix_dict, **shared})
        parent = _parented(SealFilterModel())
    else:
        monkeypatch.setattr(zh, "charm_affix_dict", {**zh.charm_affix_dict, **shared})
        parent = _parented(CharmFilterModel())
    affix = AffixFilterModel.model_construct(name="seal_x_beta", want_greater=False, value=None, min_percent_of_affix=0)
    widget = AffixWidget(affix, parent)
    rows = _rows(widget.name_combo)
    assert rows["seal_x_alpha"] != rows["seal_x_beta"]
    assert affix.name == "seal_x_beta"
    widget.name_combo.setCurrentIndex(widget.name_combo.findData("seal_x_alpha"))
    assert affix.name == "seal_x_alpha"


def test_existing_profile_roundtrips_unchanged_through_editor_widgets(zh, qapp, tmp_path) -> None:
    profile_path = tmp_path / "profiles" / "shared.yaml"
    profile_path.parent.mkdir()
    profile_path.write_text(
        "Affixes:\n- Gloves:\n    itemType: [gloves]\n    affixPool:\n    - count:\n"
        "      - {name: poison_damage}\n      - {name: shade_damage}\n"
        "Tributes:\n  name: [tribute_of_heritage]\n",
        encoding="utf-8",
    )
    store = ProfileDocumentStore(profiles_dir=profile_path.parent, full_dump=False)
    loaded = store.load(profile_path)
    original = loaded.profile.model_copy(deep=True)
    rule = next(iter(loaded.profile.affixes[0].root.values()))
    widgets = [AffixWidget(affix) for affix in rule.affix_pool[0].count]
    tab = TributesTab(loaded.profile.tributes)
    tab.load()
    for widget in widgets:
        widget.update_name(widget.name_combo.currentText())
    assert loaded.profile == original
    store.save_existing(loaded=loaded, profile=loaded.profile, source="custom")
    assert store.load(profile_path).profile == original
