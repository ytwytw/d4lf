"""Readable catalog names for native protocol values."""

from typing import TYPE_CHECKING

from src.native_filter.models import ConditionKind

if TYPE_CHECKING:
    from src.equipment_knowledge import EquipmentCatalog
    from src.native_filter.models import Condition

LABELS = {
    ConditionKind.ITEM_POWER: "物品强度范围",
    ConditionKind.RARITY: "稀有度",
    ConditionKind.PROPERTIES: "物品属性",
    ConditionKind.CODEX: "法典升级",
    ConditionKind.GREATER_AFFIX: "大词缀总数",
    ConditionKind.ITEM_TYPES: "物品类别",
    ConditionKind.REQUIRED_AFFIXES: "必需词缀",
    ConditionKind.OPTIONAL_AFFIXES: "可选词缀",
    ConditionKind.SPECIFIC_ITEMS: "指定暗金",
    ConditionKind.TALISMAN_SET: "护符套装",
}
RARITIES = {1: "普通", 2: "魔法", 4: "稀有", 8: "传奇", 16: "暗金", 32: "神话暗金", 64: "套装护符"}
PROPERTIES = {1: "普通", 4: "先祖", 32: "神话"}


def catalog_labels(catalog: EquipmentCatalog) -> dict[int, str]:
    labels: dict[int, str] = {}
    for entries, resolver in (
        (catalog.item_types, catalog.resolve_item_type),
        (catalog.items, catalog.resolve_unique),
        (catalog.affixes, catalog.resolve_affix),
    ):
        for entry in entries:
            if not entry.canonical_name:
                continue
            label = entry.name_zh or entry.name_en
            for sno_id in resolver(entry.canonical_name):
                labels.setdefault(sno_id, label)
    return labels


def id_labels(ids: tuple[int, ...], names: dict[int, str]) -> str:
    return "、".join(dict.fromkeys(names.get(sno_id, f"未知 ID {sno_id}") for sno_id in ids))


def describe_condition(condition: Condition, names: dict[int, str]) -> str:
    parts = []
    if condition.sno_ids and condition.kind != ConditionKind.TALISMAN_SET:
        parts.append(id_labels(condition.sno_ids, names))
    if condition.minimum is not None or condition.maximum is not None:
        parts.append(
            f"{condition.minimum if condition.minimum is not None else '不限'}–{condition.maximum if condition.maximum is not None else '不限'}"
        )
    if condition.mask:
        choices = RARITIES if condition.kind == ConditionKind.RARITY else PROPERTIES
        parts.append("、".join(label for value, label in choices.items() if condition.mask & value))
        unknown = condition.mask & ~sum(choices)
        if unknown:
            parts.append(f"未知标记 {unknown}")
    if condition.kind in {ConditionKind.GREATER_AFFIX, ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
        parts.append(f"至少 {condition.min_count} 条")
    if condition.ga_sno_ids:
        parts.append("其中为大词缀：" + id_labels(condition.ga_sno_ids, names))
    if condition.set_sno_id is not None:
        parts.append(f"套装 {condition.set_sno_id}；部件：{id_labels(condition.piece_sno_ids, names)}")
    if condition.kind == ConditionKind.CODEX:
        parts.append("可解锁或升级法典")
    return f"{LABELS.get(condition.kind, '未知条件')}：{'；'.join(parts)}"
