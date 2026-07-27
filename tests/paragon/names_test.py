import json
from pathlib import Path

from src.paragon.names import localized_paragon_name, paragon_class_slug

CATALOG_ROOT = Path(__file__).parents[2] / "assets" / "lang"


def test_paragon_name_catalogs_have_matching_stable_ids() -> None:
    catalogs = {}
    for locale in ("enUS", "zhCN"):
        catalogs[locale] = json.loads((CATALOG_ROOT / locale / "paragon_names.json").read_text(encoding="utf-8"))

    assert catalogs["zhCN"]["boards"].keys() == catalogs["enUS"]["boards"].keys()
    assert catalogs["zhCN"]["glyphs"].keys() == catalogs["enUS"]["glyphs"].keys()


def test_localized_paragon_name_prefers_stable_id() -> None:
    assert (
        localized_paragon_name(
            "boards", identifier="Paragon_Barb_01", source_name="Untrusted Display Text", locale="zhCN"
        )
        == "出血"
    )
    assert (
        localized_paragon_name(
            "glyphs", identifier="Rare_001_Intelligence_Main", source_name="Untrusted Display Text", locale="enUS"
        )
        == "Enchanter"
    )


def test_localized_paragon_name_matches_paired_legacy_names() -> None:
    assert localized_paragon_name("boards", identifier=None, source_name="Hemorrhage", locale="zhCN") == "出血"
    assert localized_paragon_name("glyphs", identifier=None, source_name="附魔", locale="enUS") == "Enchanter"


def test_ambiguous_legacy_glyph_name_is_not_assigned_to_an_arbitrary_class() -> None:
    assert localized_paragon_name("glyphs", identifier=None, source_name="Control", locale="zhCN") == "Control"


def test_starting_board_alias_uses_the_board_class() -> None:
    assert (
        localized_paragon_name(
            "boards", identifier=None, source_name="Starting Board", class_slug="barbarian", locale="zhCN"
        )
        == "开始"
    )


def test_paragon_class_slug_prefers_board_id() -> None:
    assert paragon_class_slug("Paragon_Sorc_04", "barbarian-wrong") == "sorcerer"
    assert paragon_class_slug(None, "necromancer-flesh-eater") == "necromancer"
