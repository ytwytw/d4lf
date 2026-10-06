"""Present recorded names and ranges without inventing absent translations."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.equipment_knowledge.catalog import EquipmentCatalog
    from src.equipment_knowledge.models import AffixEntry, EquipmentEntry
    from src.type_aliases import JsonValue

_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_UNKNOWN = "未知（来源未提供）"


def display(value: JsonValue) -> str:
    if value is None:
        return _UNKNOWN
    if isinstance(value, str):
        return re.sub(r"\{/?(?:c_[^}]*|c|u)\}", "", value)
    if isinstance(value, list):
        return "、".join(display(entry) for entry in value) or "来源记录为空"
    if isinstance(value, dict):
        return "；".join(f"{key}：{display(entry)}" for key, entry in value.items())
    return str(value)


def affix_template(value: JsonValue) -> str:
    """Show a variable placeholder without exposing source formatting formulas."""
    text = display(value)
    text = re.sub(r"\[\{VALUE\}([^\]]*)\]", lambda match: "[浮动值]%" if "%" in match[1] else "[浮动值]", text)
    return text.replace("{VALUE}", "浮动值")


def localized_affix(key: str, description: str, catalog: EquipmentCatalog) -> str:
    """Only substitute source numbers when both translated templates agree."""
    description = display(description)
    for affix in catalog.affixes_for_key(key):
        english = display(affix.name_en)
        chinese = display(affix.name_zh) if affix.name_zh else None
        if not chinese:
            continue
        if english == description:
            return f"{chinese} / {description}"
        if _NUMBER.sub("#", english) == _NUMBER.sub("#", description) and _NUMBER.findall(english) == _NUMBER.findall(
            chinese
        ):
            values = iter(_NUMBER.findall(description))
            localized = _NUMBER.sub(lambda _match, values=values: next(values), chinese)
            return f"{localized} / {description}（同身份中文模板，数值取本装备英文来源）"
    return f"{description}（此装备描述的对应中文未知）"


def affix_details(affix: AffixEntry) -> str:
    lines = [
        f"{display(affix.name_zh)} / {display(affix.name_en)}",
        f"适用部位：{display(affix.raw_en.get('itemType'))}",
        f"适用职业：{display(affix.raw_en.get('charType'))}",
        f"词条身份（中文）：{affix_template((affix.raw_zh or {}).get('descTpl'))}",
        f"词条身份（英文）：{affix_template(affix.raw_en.get('descTpl'))}",
        "按物品强度的通用范围（原始数据单位，百分比等请对照上方描述）：",
    ]
    ranges = affix.raw_en.get("effectList")
    if isinstance(ranges, list) and ranges:
        lines.extend(
            f"  强度 {entry.get('ipower', '未知')}：{entry.get('min', '未知')} — {entry.get('max', '未知')}"
            for entry in ranges
            if isinstance(entry, dict)
        )
    else:
        lines.append(f"  {_UNKNOWN}")
    lines.extend(("", f"词条身份：{affix.key} · SNO {affix.sno_id}"))
    return "\n".join(lines)


def _identity_lines(keys: JsonValue, catalog: EquipmentCatalog) -> list[str]:
    if not isinstance(keys, list):
        return [_UNKNOWN]
    lines = []
    for key in keys:
        if not isinstance(key, str):
            continue
        matches = catalog.affixes_for_key(key)
        names = sorted({
            affix_template(
                (match.raw_zh or {}).get("descTpl") or match.raw_en.get("descTpl") or match.name_zh or match.name_en
            )
            for match in matches
        })
        lines.append(f"• {' / '.join(names) if names else '名称未知'} 〔{key}〕")
    return lines or ["来源记录为空"]


def _choice_lines(item: EquipmentEntry, catalog: EquipmentCatalog) -> list[str]:
    groups = item.raw_en.get("affixChoices")
    if not isinstance(groups, list):
        return []
    lines = ["", "可选词条组（各组选择一项，非同时固定拥有）"]
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            continue
        lines.append(f"第 {index} 组：")
        options = group.get("options")
        if not isinstance(options, list):
            lines.append(_UNKNOWN)
            continue
        for option in options:
            if isinstance(option, dict) and isinstance(option.get("key"), str):
                key = str(option["key"])
                lines.extend((
                    f"• {localized_affix(key, display(option.get('desc')), catalog)}",
                    f"  适用职业：{display(option.get('char'))}；身份：{key}",
                ))
    return lines


def _class_lines(item: EquipmentEntry, catalog: EquipmentCatalog) -> list[str]:
    classes = item.raw_en.get("classAffixes")
    if not isinstance(classes, dict):
        return []
    lines = ["", "按职业变化的词条（只使用对应职业项）"]
    for name, record in classes.items():
        if not isinstance(record, dict):
            continue
        lines.append(f"{name}：")
        keys, descriptions = record.get("explicits"), record.get("affixesDesc")
        if isinstance(keys, list) and isinstance(descriptions, list) and len(keys) == len(descriptions):
            lines.extend(
                f"• {localized_affix(str(key), display(desc), catalog)}"
                for key, desc in zip(keys, descriptions, strict=True)
            )
        else:
            lines.append(display(descriptions))
        lines.append(f"  身份：{display(keys)}")
    return lines


def _recipe_lines(item: EquipmentEntry) -> list[str]:
    recipe = item.raw_en.get("runewordRecipe")
    if not isinstance(recipe, list):
        return []
    localized = (item.raw_zh or {}).get("runewordRecipe")
    chinese = (
        {(rune.get("key"), rune.get("id")): rune.get("name") for rune in localized if isinstance(rune, dict)}
        if isinstance(localized, list)
        else {}
    )
    names = [
        f"{display(chinese.get((rune.get('key'), rune.get('id'))))} / {display(rune.get('name'))}"
        for rune in recipe
        if isinstance(rune, dict)
    ]
    return ["", "符文之语配方（按来源顺序，重复符文保留）", " → ".join(names)]


def item_details(item: EquipmentEntry, catalog: EquipmentCatalog) -> str:
    zh = item.raw_zh or {}
    drops = zh.get("dropBoss", item.raw_en.get("dropBoss"))
    source = display(drops).replace("WorldDrop", "世界掉落（WorldDrop）")
    lines = [
        f"{item.name_zh or '中文名称未知'} / {item.name_en}",
        f"部位：{display(zh.get('equipTypeName'))} / {item.item_type}",
        f"职业：{display(item.raw_en.get('char'))}",
        f"资料版本：{catalog.game_version} · 快照 {catalog.data.snapshot_date}",
        "",
        "掉落来源",
        source,
        "除已核验标签外，来源名按数据原文显示；未提供的中文名称和掉率均为未知。",
        "",
        "物品描述与浮动范围（按物品原文，非当前背包装备数值）",
    ]
    for title, record in (("中文", zh), ("英文", item.raw_en)):
        descriptions = record.get("affixesDesc")
        lines.append(f"{title}：")
        if isinstance(descriptions, list):
            lines.extend(f"  {display(value)}" for value in descriptions)
        else:
            lines.append(_UNKNOWN)
    for key, title in (("armor", "护甲／抗性"), ("damage", "伤害"), ("damageDetails", "伤害细节")):
        if key in item.raw_en or key in zh:
            lines.extend(("", title, f"中文：{display(zh.get(key))}", f"英文：{display(item.raw_en.get(key))}"))
    lines.extend((
        "",
        "词条身份与数值范围",
        "下方区分来源指定的固有词条与主要词条身份；身份确定不代表数值固定，方括号区间表示浮动范围。",
        "可选词条组与职业变化另列；不同装备的固定词条数量可能不同。",
    ))
    for field, title in (("implicits", "来源列出的固有词条"), ("explicits", "来源指定的主要词条身份")):
        lines.extend(("", title, "名称为通用词条资料；本装备实际浮动范围以上方装备原文为准。"))
        lines.extend(_identity_lines(item.raw_en.get(field), catalog))
        if field == "implicits" and "implict" in item.raw_en:
            lines.append(f"本装备固有词条原文：{display(item.raw_en['implict'])}")
    lines.extend(_choice_lines(item, catalog))
    lines.extend(_class_lines(item, catalog))
    lines.extend(_recipe_lines(item))
    lines.extend((
        "",
        "资料身份与来源",
        f"{item.key} · SNO {item.sno_id}",
        catalog.source,
        "中文与英文使用相同物品 key + SNO 配对；中文缺失字段不会用英文冒充中文。",
        "英文扩展字段可能早于中文更新；以上为版本化资料，不保证等同当前游戏。",
        "此列表涵盖来源中的具名装备；普通传奇的随机词条与打造来源未作为完整装备图鉴收录。",
    ))
    return "\n".join(lines)
