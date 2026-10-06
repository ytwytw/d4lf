import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog
from src.game_data import catalog as catalog_module

_ROOT = Path(__file__).parents[2]
_EXPECTED = [
    ("greater_tribute_of_armaments", "强效军械贡品", 2125047, "X1_Undercity_TributeKeySigil_GreaterAffixes_Party"),
    ("greater_tribute_of_harmony", "强效和谐贡品", 2581879, "X2_Undercity_TributeKeySigil_Runes_Greater"),
    (
        "greater_tribute_of_ingenuity",
        "强效巧思贡品",
        2580967,
        "X2_Undercity_TributeKeySigil_CraftingMaterials_Cube_Greater",
    ),
    ("greater_tribute_of_the_horadrim", "大型赫拉迪姆的贡品", 2580937, "X2_Undercity_TributeKeySigil_Talisman_Greater"),
    ("lesser_tribute", "小型贡品", 2625218, "X1_Undercity_TributeKeySigil_RandomMagic"),
    (
        "lesser_tribute_of_ingenuity",
        "次级巧思贡品",
        2581866,
        "X2_Undercity_TributeKeySigil_CraftingMaterials_Cube_Lesser",
    ),
    ("lesser_tribute_of_the_horadrim", "小型赫拉迪姆的贡品", 2580953, "X2_Undercity_TributeKeySigil_Talisman_Lesser"),
    ("major_tribute_of_andariel", "安达莉尔的大型贡品", 2485152, "S11_Undercity_TributeKeySigil_Andariel_3"),
    ("minor_tribute_of_andariel", "安达莉尔的小型贡品", 2447394, "S11_Undercity_TributeKeySigil_Andariel_1"),
    ("tribute_of_andariel", "安达莉尔的贡品", 2485144, "S11_Undercity_TributeKeySigil_Andariel_2"),
    ("tribute_of_heritage", "巨人贡品", 2077993, "X1_Undercity_TributeKeySigil_ClassUniques"),
    ("tribute_of_the_horadrim", "赫拉迪姆的贡品", 2326828, "X1_Undercity_TributeKeySigil_Talisman"),
]


def _load_catalog(monkeypatch: pytest.MonkeyPatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    return catalog


def test_reviewed_tribute_names_resolve_without_guessing_shared_name(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = _load_catalog(monkeypatch)

    for canonical, name, _, _ in _EXPECTED:
        assert catalog.tribute_dict[canonical] == name
        assert catalog.resolve_tribute(canonical) == canonical
        assert catalog.resolve_tribute(name) == (None if name == "巨人贡品" else canonical)
    assert catalog.resolve_tribute("tribute_of_titans") == "tribute_of_titans"
    assert catalog.resolve_tribute("巨人贡品") is None
    assert catalog.resolve_tribute("不存在的贡品") is None


@pytest.mark.parametrize(("canonical", "name", "item_sno", "internal_key"), _EXPECTED)
def test_tribute_names_are_bound_to_reviewed_source_identity(
    canonical: str, name: str, item_sno: int, internal_key: str
) -> None:
    locale = _ROOT / "assets/lang/zhCN"
    manifest = json.loads((locale / "manifest.json").read_text(encoding="utf-8"))
    reviewed = json.loads((_ROOT / "src/tools/data/reviewed_zhCN.json").read_text(encoding="utf-8"))
    english = json.loads((_ROOT / "assets/lang/enUS/tributes.json").read_text(encoding="utf-8"))
    stable_id = f"tributes:{canonical}"
    record = next(record for record in manifest["records"] if record["stable_id"] == stable_id)
    source = record["translation_source"]

    assert reviewed["records"][stable_id] == record["text"] == name
    assert record["source_sha256"] == hashlib.sha256(english[canonical].encode("utf-8")).hexdigest()
    assert source["translation_sha256"] == hashlib.sha256(name.encode("utf-8")).hexdigest()
    assert source["provider"] == "reviewed_override"
    assert source["reference_provider"] == "wowhead"
    assert source["source_item_id"] == item_sno
    assert source["source_item_key"] == internal_key
    assert source["source_data_version"] == "3.0.2"
    assert source["scope"] == "identity_matched_database_name; not live_game_verified"
    assert "game_build" not in source
    assert "capture_fixture" not in source
    reference = source["reference_files"][0]
    assert reference["url"] == f"https://www.wowhead.com/diablo-4/cn/item/{canonical.replace('_', '-')}-{item_sno}"
    assert len(reference["sha256"]) == 64
    assert int(reference["sha256"], 16) > 0


def test_completed_tribute_names_keep_two_ambiguities_and_live_acceptance_gate() -> None:
    locale = _ROOT / "assets/lang/zhCN"
    quality = json.loads((locale / "quality-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((locale / "manifest.json").read_text(encoding="utf-8"))
    tributes = json.loads((locale / "tributes.json").read_text(encoding="utf-8"))

    assert all(tributes.values())
    assert not any(entry["stable_id"].startswith("tributes:") for entry in quality["unresolved"])
    assert quality["summary"]["unresolved_by_kind"].get("tributes", 0) == 0
    assert (
        quality["summary"]["resolved_records"] + quality["summary"]["unresolved_records"]
        == quality["summary"]["source_records"]
    )
    collisions = quality["selected_quality"]["alias_collisions"]
    assert {
        (entry["namespace"], entry["normalized_alias"])
        for entry in collisions
        if entry["namespace"] in ("aspects", "tributes")
    } == {("aspects", "恶毒"), ("tributes", "巨人贡品")}
    tribute_collision = next(entry for entry in collisions if entry["namespace"] == "tributes")
    assert set(tribute_collision["stable_ids"]) == {"tribute_of_heritage", "tribute_of_titans"}
    assert quality["source_builds"]["wowhead"] == "3.0.2"
    assert quality["summary"]["source_builds_match"] is False
    assert manifest["runtime_ready"] is quality["runtime_ready"] is False
    assert manifest["source_quality_ok"] is quality["summary"]["source_quality_ok"] is False
    assert len(manifest["readiness_blockers"]) == len(quality["readiness_blockers"]) == 2
