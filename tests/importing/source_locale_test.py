from src.importing.source_locale import match_source_affix, source_affix_dict_for_item_type
from src.item import ItemType


def test_source_affix_catalog_is_selected_explicitly() -> None:
    english = source_affix_dict_for_item_type(ItemType.Ring, "enUS")
    chinese = source_affix_dict_for_item_type(ItemType.Ring, "zhCN")

    assert english["maximum_life"] == "maximum life"
    assert chinese["maximum_life"] == "生命上限"


def test_source_affix_matching_returns_the_same_canonical_key_for_both_languages() -> None:
    assert match_source_affix("Maximum Life", ItemType.Ring, "enUS") == "maximum_life"
    assert match_source_affix("生命上限", ItemType.Ring, "zhCN") == "maximum_life"


def test_source_affix_matching_is_exact_and_fails_closed() -> None:
    assert match_source_affix("Maximum Lif", ItemType.Ring, "enUS") is None
    assert match_source_affix("new season unknown stat", ItemType.Ring, "enUS") is None


def test_source_catalog_falls_back_to_english_for_missing_chinese_seal_keys() -> None:
    english = source_affix_dict_for_item_type(ItemType.Ring, "enUS")
    chinese = source_affix_dict_for_item_type(ItemType.Ring, "zhCN")

    assert chinese["crafting_material_drop_rate"] == english["crafting_material_drop_rate"]
