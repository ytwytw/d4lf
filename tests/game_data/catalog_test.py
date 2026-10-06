import hashlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog, ItemType
from src.game_data import catalog as catalog_module
from src.item import Item, ItemJSONEncoder


class _LoaderFailure(BaseException):
    pass


def _load_zhcn_catalog(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    return catalog


def test_catalog_has_expected_data_containers() -> None:
    assert isinstance(GameCatalog.affix_dict, dict)
    assert isinstance(GameCatalog.aspect_list, list)


def test_catalog_reload_keeps_item_type_values_canonical() -> None:
    catalog = GameCatalog()
    canonical_values = {item_type: item_type.value for item_type in ItemType}

    catalog.load_data()

    assert {item_type: item_type.value for item_type in ItemType} == canonical_values


def test_catalog_resolves_item_type_names_values_and_labels(monkeypatch) -> None:
    catalog = GameCatalog()
    monkeypatch.setattr(catalog, "item_types_dict", {**catalog.item_types_dict, "Helm": "Casque", "Incense": "Encens"})

    assert catalog.item_type_label(ItemType.Helm) == "Casque"
    assert catalog.item_type_from_text("Helm") is ItemType.Helm
    assert catalog.item_type_from_text("helm") is ItemType.Helm
    assert catalog.item_type_from_text("  casque ") is ItemType.Helm
    assert catalog.item_type_from_text("encens") is ItemType.Incense
    assert catalog.item_type_from_text("unknown") is None


def test_zhcn_catalog_loads_runtime_aliases(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_affix("闪避给予的移动速度，持续 秒") == "evade_grants_movement_speed_for_seconds"
    assert catalog.resolve_tribute("巨人贡品") is None
    assert catalog.resolve_item_type("胸甲") == "ChestArmor"
    assert catalog.item_type_from_text("胸甲") is ItemType.ChestArmor
    assert catalog.resolve_unique("命运之拳") == "fists_of_fate"
    assert catalog.item_type_from_text("神符") is ItemType.Charm
    assert catalog.item_type_from_text("赫拉迪姆封印") is ItemType.HoradricSeal
    assert catalog.item_type_from_text("horadric seal") is ItemType.HoradricSeal


def test_shared_chinese_aspect_label_does_not_imply_equivalent_powers(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_aspect("恶毒之胸甲") is None
    assert catalog.resolve_aspect("malicious") == "malicious"
    assert catalog.resolve_aspect("virulent") == "virulent"


@pytest.mark.parametrize(
    ("item_type", "expected"),
    [
        (None, None),
        (ItemType.Sword, None),
        (ItemType.Axe2H, "ancients_oath"),
        (ItemType.Focus, "ancients_pledge"),
        (ItemType.OffHandTotem, "ancients_pledge"),
        (ItemType.Shield, "ancients_pledge"),
    ],
)
def test_shared_unique_translation_requires_verified_item_type(monkeypatch, item_type, expected) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_unique("先祖之誓", item_type=item_type) == expected


@pytest.mark.parametrize("canonical", ["ancients_oath", "ancients_pledge"])
@pytest.mark.parametrize("item_types", [None, [], "Shield", ["Unknown"], ["Shield", "Unknown"], [123]])
def test_incomplete_type_metadata_cannot_eliminate_a_shared_name_candidate(monkeypatch, canonical, item_types) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)
    catalog.aspect_unique_dict[canonical]["item_types"] = item_types

    assert catalog.resolve_unique("先祖之誓", item_type=ItemType.Axe2H) is None
    assert catalog.resolve_unique("先祖之誓", item_type=ItemType.Shield) is None


def test_overlapping_type_metadata_cannot_resolve_a_shared_unique_name(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)
    catalog.aspect_unique_dict["ancients_pledge"]["item_types"] = ["Axe2H", "Shield"]

    assert catalog.resolve_unique("先祖之誓", item_type=ItemType.Axe2H) is None


@pytest.mark.parametrize("canonical", ["ancients_oath", "ancients_pledge"])
def test_shared_unique_preserves_canonical_and_english_aliases_without_type(monkeypatch, canonical) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_unique(canonical) == canonical
    assert catalog.resolve_unique(canonical.replace("_", " ")) == canonical


def test_zhcn_catalog_contains_season_15_upstream_delta(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_affix("金币掉落几率") == "gold_drop_rate"
    assert catalog.resolve_tribute("强效精炼贡品") == "greater_tribute_of_refinement"
    assert catalog.resolve_tribute("巧思贡品") == "tribute_of_ingenuity"
    assert catalog.resolve_tribute("次级和谐贡品") == "lesser_tribute_of_harmony"
    expected_uniques = {
        "艾里欧克之针": "ariocs_needle",
        "亨利的永恒追捕": "henris_perquisition",
        "寅剑": "in-geom",
        "复仇者护腕": "nemesis_bracers",
        "斯奎特的罩衫": "squirts_blouse",
        "乔丹之石": "stone_of_jordan",
        "焚炉": "the_furnace",
    }
    assert {name: catalog.resolve_unique(name) for name in expected_uniques} == expected_uniques


def test_zhcn_manifest_locks_runtime_files_and_review_sources() -> None:
    root = Path(__file__).parents[2]
    locale_dir = root / "assets/lang/zhCN"
    manifest = json.loads((locale_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["build_version"] == "3.2.1.73552"
    for entry in manifest["files"]:
        payload = (locale_dir / entry["path"]).read_bytes()
        assert b"\r\n" not in payload, entry["path"]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
    assert (
        hashlib.sha256((root / "assets/catalog/source-lock.json").read_bytes()).hexdigest()
        == manifest["source_lock_sha256"]
    )
    reviewed_path = locale_dir / manifest["reviewed_overrides"]["path"]
    assert hashlib.sha256(reviewed_path.resolve().read_bytes()).hexdigest() == manifest["reviewed_overrides"]["sha256"]


def test_zhcn_manifest_matches_runtime_text_and_reports_remaining_release_gaps() -> None:
    locale_dir = Path(__file__).parents[2] / "assets/lang/zhCN"
    manifest = json.loads((locale_dir / "manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((locale_dir / "quality-report.json").read_text(encoding="utf-8"))
    datasets = {
        entry["path"].removesuffix(".json"): json.loads((locale_dir / entry["path"]).read_text(encoding="utf-8"))
        for entry in manifest["files"]
    }
    records = manifest["records"]
    assert len({record["stable_id"] for record in records}) == len(records)
    assert quality["summary"]["resolved_records"] == len(records)
    assert quality["summary"]["unresolved_records"] == len(quality["unresolved"])
    for record in records:
        namespace, *keys = record["stable_id"].split(":")
        value = datasets[namespace]
        for key in keys:
            value = value[key]
        if namespace == "uniques":
            value = value["display_name"]
        assert value == record["text"], record["stable_id"]
        assert hashlib.sha256(value.encode("utf-8")).hexdigest() == record["translation_source"]["translation_sha256"]
        source = record["translation_source"]
        if fixture_hash := source.get("capture_fixture_sha256"):
            fixture_path = locale_dir.parents[2] / source["capture_fixture"]
            fixture_bytes = fixture_path.read_bytes()
            assert b"\r\n" not in fixture_bytes
            assert hashlib.sha256(fixture_bytes).hexdigest() == fixture_hash
    if quality["unresolved"] or quality["selected_quality"]["alias_collisions"]:
        assert manifest["runtime_ready"] is False
        assert quality["runtime_ready"] is False
        assert manifest["readiness_blockers"]
        assert quality["readiness_blockers"]


def test_zhcn_catalog_uses_reviewed_translations(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.affix_dict["crafting_material_drop_rate"] == "制作材料掉率"
    assert catalog.charm_affix_dict["crafting_material_drop_rate"] == "制作材料掉率"
    assert catalog.affix_sigil_dict_all["positive"]["ruptures"] == "混沌裂隙"
    assert catalog.tribute_dict["greater_tribute_of_armaments"] == "强效军械贡品"


def test_zhcn_ambiguous_damage_aliases_use_range_precision(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_affix_exact("暗影伤害") is None
    assert catalog.resolve_affix_exact("暗影伤害", range_precision="decimal") == "shade_damage"
    assert catalog.resolve_affix_exact("暗影伤害", range_precision="integer") == "shadow_damage"
    assert catalog.resolve_affix_exact("毒素伤害", range_precision="decimal") == "poisoning_damage"
    assert catalog.resolve_affix_exact("毒素伤害", range_precision="integer") == "poison_damage"


def test_item_type_serialization_uses_canonical_value_after_catalog_load() -> None:
    catalog = GameCatalog()
    catalog.load_data()

    encoded = json.dumps(Item(item_type=ItemType.Incense), cls=ItemJSONEncoder)

    assert '"item_type": "incense"' in encoded


def test_catalog_retries_after_failed_initialization(monkeypatch) -> None:
    monkeypatch.setattr(GameCatalog, "_instance", None)
    monkeypatch.setattr(GameCatalog, "data_loaded", False)
    attempts = 0

    def load_data(instance) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            message = "load failed"
            raise RuntimeError(message)
        instance.affix_dict = {"ready": "yes"}

    monkeypatch.setattr(GameCatalog, "load_data", load_data)
    with pytest.raises(RuntimeError, match="load failed"):
        GameCatalog()
    assert GameCatalog._instance is None
    assert GameCatalog.data_loaded is False

    instance = GameCatalog()
    assert instance.data_loaded is True
    assert instance.affix_dict == {"ready": "yes"}


def test_catalog_initialization_is_serialized(monkeypatch) -> None:
    monkeypatch.setattr(GameCatalog, "_instance", None)
    monkeypatch.setattr(GameCatalog, "data_loaded", False)
    started = threading.Event()
    release = threading.Event()
    instances = []

    def load_data(instance) -> None:
        started.set()
        assert release.wait(timeout=2)
        instance.aspect_list = ["ready"]

    monkeypatch.setattr(GameCatalog, "load_data", load_data)
    first = threading.Thread(target=lambda: instances.append(GameCatalog()))
    second = threading.Thread(target=lambda: instances.append(GameCatalog()))
    first.start()
    assert started.wait(timeout=1)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert instances[0] is instances[1]
    assert instances[0].aspect_list == ["ready"]
    assert catalog_module.GAME_CATALOG_LOCK is not None
