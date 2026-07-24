import os

import pytest
from PyQt6.QtWidgets import QApplication, QGroupBox, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.config.profile_models import AffixFilterModel, AspectUniqueFilterModel, CharmFilterModel, SealFilterModel
from src.gui.models import catalog_display
from src.gui.profile_editor.affixes_tab import AffixWidget, ItemTypePicker, UniqueAspectWidget, _item_type_summary
from src.item.data.item_type import ItemType


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class MockGroupEditor(QWidget):
    """Mock group editor to act as a parent with a config attribute."""

    def __init__(self, config):
        super().__init__()
        self.config = config

    def update_greater_count_label(self):
        pass

    def sync_min_greater_from_checkboxes(self):
        pass


def test_affix_widget_parent_config(qapp, mock_ini_loader):
    # Test that only SealFilterModel is recognized as a parent seal config
    seal_config = SealFilterModel(affix_pool=[])
    charm_config = CharmFilterModel(affix_pool=[])

    affix = AffixFilterModel(name="movement_speed", value=None)

    parent_seal = MockGroupEditor(seal_config)
    widget_seal = AffixWidget(affix, parent=parent_seal)
    assert widget_seal.get_parent_seal_config() is seal_config

    parent_charm = MockGroupEditor(charm_config)
    widget_charm = AffixWidget(affix, parent=parent_charm)
    assert widget_charm.get_parent_seal_config() is None


def test_affix_widget_clears_on_empty_filter(qapp, mock_ini_loader):
    # Test that if name_combo has no items, update_name clears self.affix.name (for seals)
    affix = AffixFilterModel(name="adept_action_damage_reduction_while_moving", value=None)
    seal_config = SealFilterModel(affix_pool=[])

    parent = MockGroupEditor(seal_config)
    widget = AffixWidget(affix, parent=parent)

    # Initially it should match adept_action_damage_reduction_while_moving
    assert widget.affix.name == "adept_action_damage_reduction_while_moving"

    # Set filtered_affixes to empty to simulate a set change filtering out all options
    widget.filtered_affixes = {}
    widget.name_combo.clear()

    # Call update_name with empty string
    widget.update_name("")

    # It must clear the name
    assert not widget.affix.name


def test_item_type_picker_localizes_labels_but_returns_enum_values(qapp, monkeypatch):
    catalog = type(
        "Catalog",
        (),
        {
            "grammar": type("Grammar", (), {"locale": "zhCN"})(),
            "item_types_dict": {"Sword": "剑", "Helm": "头盔"},
            "resolve_item_type": lambda _self, value: value,
        },
    )()
    monkeypatch.setattr(catalog_display, "Dataloader", lambda: catalog)
    monkeypatch.setattr(
        catalog_display,
        "IniConfigLoader",
        lambda: type("Config", (), {"general": type("General", (), {"language": "zhCN"})()})(),
    )

    parent = QWidget()
    picker = ItemTypePicker(parent, [ItemType.Sword, ItemType.Helm], [ItemType.Helm])

    assert _item_type_summary([ItemType.Sword, ItemType.Helm]) == "剑, 头盔"
    assert {group.title() for group in picker.findChildren(QGroupBox)} == {"武器", "非武器"}
    assert picker.checkboxes[ItemType.Sword].text() == "剑"
    assert picker.checkboxes[ItemType.Helm].text() == "头盔"
    assert picker.get_selected_item_types() == [ItemType.Helm]


def test_unique_aspect_combo_displays_localized_name_and_stores_canonical_id(qapp, mock_ini_loader, monkeypatch):
    catalog = type(
        "Catalog",
        (),
        {
            "grammar": type("Grammar", (), {"locale": "zhCN"})(),
            "aspect_unique_dict": {
                "first_unique": {"display_name": "第一件暗金"},
                "second_unique": {"display_name": "第二件暗金"},
            },
            "resolve_unique": lambda _self, value: {"第一件暗金": "first_unique", "第二件暗金": "second_unique"}.get(
                value
            ),
        },
    )()
    monkeypatch.setattr(catalog_display, "Dataloader", lambda: catalog)
    monkeypatch.setattr(
        catalog_display,
        "IniConfigLoader",
        lambda: type("Config", (), {"general": type("General", (), {"language": "zhCN"})()})(),
    )
    monkeypatch.setattr("src.gui.profile_editor.affixes_tab.Dataloader", lambda: catalog)
    unique_aspect = AspectUniqueFilterModel.model_construct(name="first_unique", value=None, min_percent_of_aspect=0)

    widget = UniqueAspectWidget(unique_aspect)
    assert widget.name_combo.currentText() == "第一件暗金"
    assert widget.name_combo.currentData() == "first_unique"

    widget.name_combo.setCurrentIndex(widget.name_combo.findData("second_unique"))
    assert unique_aspect.name == "second_unique"

    widget.name_combo.setCurrentIndex(widget.name_combo.findData("first_unique"))
    widget.name_combo.setEditText("第二件暗金")
    assert unique_aspect.name == "second_unique"
