from src.equipment_knowledge import load_catalog
from src.equipment_knowledge.formatting import affix_template, display, item_details, localized_affix


def test_optional_affix_ranges_use_equipment_values_and_recipe_preserves_duplicates():
    catalog = load_catalog()
    item = next(item for item in catalog.items if item.key == "Runeword_Infinity_2HScythe")
    assert item.raw_zh is not None
    assert item.raw_zh["affixChoices"] == [
        {
            "family": 2955432778,
            "label": "以下属性随机一种",
            "classNames": {"Necromancer": "死灵法师"},
            "options": [
                {"key": "Runeword_DamageType_Shadow", "char": ["Necromancer"], "desc": "x[45 - 55]% 暗影 伤害增倍"},
                {"key": "Runeword_DamageType_Cold", "char": ["Necromancer"], "desc": "x[45 - 55]% 冰霜 伤害增倍"},
                {"key": "Runeword_DamageType_Physical", "char": ["Necromancer"], "desc": "x[45 - 55]% 物理 伤害增倍"},
            ],
        }
    ]
    detail = item_details(item, catalog)
    assert "各组选择一项，非同时固定拥有" in detail
    assert "x[45 - 55]% 冰霜" in detail
    assert "Shadow Damage Multiplier" in detail
    assert "同身份中文模板，数值取本装备英文来源" in detail
    assert "贝 / Ber → 玛尔 / Mal → 贝 / Ber → 伊斯特 / Ist" in detail
    assert '"family"' not in detail
    assert "SNO" in detail


def test_fists_details_include_actual_range_and_source_without_probabilities():
    catalog = load_catalog()
    detail = item_details(catalog.search("命运之拳")[0], catalog)
    assert "世界掉落（WorldDrop）" in detail
    assert "250 - 300" in detail
    assert "S04_Luck" in detail
    assert "掉率均为未知" in detail
    assert "普通传奇" in detail
    assert "[8.0 - 9.0]" not in detail
    assert "身份确定不代表数值固定" in detail
    assert "+[浮动值]% 幸运一击几率" in detail
    assert "*100|" not in detail


def test_unknown_or_different_affix_description_is_not_fabricated_chinese():
    catalog = load_catalog()
    assert "对应中文未知" in localized_affix("Runeword_DamageType_Cold", "Unrelated 99 effect", catalog)
    assert "对应中文未知" in localized_affix("unknown", "Another effect", catalog)
    assert display(None) == "未知（来源未提供）"
    assert display("{c_gold}text{/c}") == "text"


def test_class_specific_affixes_are_readable_and_kept_separate():
    catalog = load_catalog()
    item = next(item for item in catalog.items if "classAffixes" in item.raw_en)
    detail = item_details(item, catalog)
    assert "只使用对应职业项" in detail
    assert '"affixesDesc"' not in detail


def test_affix_templates_preserve_units_without_source_formula_markers():
    assert affix_template("+[{VALUE} * 100|1%|] 攻击速度") == "+[浮动值]% 攻击速度"
    assert affix_template("[{VALUE}|~|] 点智力") == "[浮动值] 点智力"
    assert affix_template("攻击使闪避的冷却时间缩短 [{VALUE}|1|] 秒") == "攻击使闪避的冷却时间缩短 [浮动值] 秒"
    assert (
        affix_template("幸运一击: 最多有 15% 几率恢复 +[{VALUE}] 主要资源")
        == "幸运一击: 最多有 15% 几率恢复 +[浮动值] 主要资源"
    )
    assert affix_template(None) == "未知（来源未提供）"
