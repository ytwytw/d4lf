from src.game_data import ItemType
from src.importing import source_locale
from src.importing.source_locale import match_source_affix, source_affix_dict_for_item_type


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


def test_source_catalog_uses_verified_chinese_crafting_material_label() -> None:
    for item_type in (ItemType.Ring, ItemType.Charm):
        chinese = source_affix_dict_for_item_type(item_type, "zhCN")
        assert chinese["crafting_material_drop_rate"] == "制作材料掉率"
        assert match_source_affix("制作材料掉率", item_type, "zhCN") == "crafting_material_drop_rate"


def test_source_catalog_falls_back_to_english_for_missing_chinese_seal_keys(monkeypatch) -> None:
    # Exercise a genuinely absent key without depending on production translation gaps staying open.
    maps = {
        "enUS": {"all_stats": "all stats", "mastery_to_all_skills": "mastery to all skills"},
        "zhCN": {"all_stats": "全属性"},
    }

    def load_map(locale: str, file_name: str) -> dict[str, str]:
        assert file_name == "seals_affixes.json"
        return maps[locale]

    monkeypatch.setattr(source_locale, "_load_string_map", load_map)
    chinese = source_affix_dict_for_item_type.__wrapped__(ItemType.HoradricSeal, "zhCN")

    assert chinese["all_stats"] == "全属性"
    assert chinese["mastery_to_all_skills"] == "mastery to all skills"
