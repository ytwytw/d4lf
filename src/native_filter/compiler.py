"""Compile a conservative superset of Profile keep/skip decisions."""

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.game_data import ItemType, is_armor, is_jewelry, is_weapon
from src.native_filter.models import MAX_RULES, Action, CompilationResult, Condition, ConditionKind, NativeFilter, Rule

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.equipment_knowledge import EquipmentCatalog
    from src.profiles import ItemFilterModel, ProfileModel
    from src.settings import GeneralModel

RARITY_MASKS = {"common": 1, "magic": 2, "rare": 4, "legendary": 8, "unique": 16, "mythic": 32}


@dataclass(frozen=True)
class CompilePolicy:
    filter_equipment: bool = True
    keep_aspects: str = "upgrade"
    handle_uniques: str = "favorite"
    handle_cosmetics: str = "ignore"
    preserve_sanctified: bool = True
    # The native protocol has no verified "ancestral" condition, so this protection can only block hiding.
    protect_ancestral_legendaries: bool = False

    @classmethod
    def from_settings(cls, settings: GeneralModel) -> CompilePolicy:
        return cls(
            filter_equipment=settings.filter_equipment,
            keep_aspects=str(settings.keep_aspects),
            handle_uniques=str(settings.handle_uniques),
            handle_cosmetics=str(settings.handle_cosmetics),
            protect_ancestral_legendaries=settings.do_not_junk_ancestral_legendaries,
        )


def profile_scope_warnings(selected: str, enabled: Iterable[str]) -> tuple[str, ...]:
    """D4LF evaluates every enabled Profile; a native filter only ever contains the selected one."""
    others = [name for name in dict.fromkeys(entry.strip() for entry in enabled) if name and name != selected]
    if not others:
        return ()
    message = (
        f"此游戏过滤器只编译所选 Profile「{selected}」；D4LF 还启用了 {'、'.join(others)}。"
        "仅由这些 Profile 保留的装备不在此过滤器的保留规则中，启用隐藏时可能被隐藏。"
    )
    return (message,)


def profile_digest(profile: ProfileModel) -> str:
    return hashlib.sha256(profile.model_dump_json().encode("utf-8")).hexdigest()


def _mapped(names: list[str], catalog: EquipmentCatalog, kind: str) -> tuple[int, ...]:
    resolver = {"type": catalog.resolve_item_type, "affix": catalog.resolve_affix, "unique": catalog.resolve_unique}[
        kind
    ]
    resolved = [resolver(name) for name in names]
    return tuple(dict.fromkeys(sno for ids in resolved for sno in ids)) if all(resolved) else ()


def _compile_rule(name: str, spec: ItemFilterModel, catalog: EquipmentCatalog, warnings: list[str]) -> Rule:
    conditions: list[Condition] = []
    if spec.item_type:
        ids = _mapped([item_type.value for item_type in spec.item_type], catalog, "type")
        if ids:
            conditions.append(Condition(ConditionKind.ITEM_TYPES, sno_ids=ids))
        else:
            warnings.append(f"{name}：部位 SNO 映射不完整，已放宽部位限制，避免隐藏目标。")
    if spec.min_power:
        conditions.append(Condition(ConditionKind.ITEM_POWER, minimum=spec.min_power))
    if spec.rarities:
        mask = sum({RARITY_MASKS.get(rarity.value, 0) for rarity in spec.rarities})
        if mask:
            conditions.append(Condition(ConditionKind.RARITY, mask=mask))
    if spec.min_greater_affix_count:
        conditions.append(Condition(ConditionKind.GREATER_AFFIX, min_count=spec.min_greater_affix_count))
    if spec.unique_aspect:
        ids = _mapped([aspect.name for aspect in spec.unique_aspect], catalog, "unique")
        if ids:
            conditions.append(Condition(ConditionKind.SPECIFIC_ITEMS, sno_ids=ids))
        else:
            warnings.append(f"{name}：暗金映射不完整，已放宽暗金名称限制。")
        if any(aspect.value is not None or aspect.min_percent_of_aspect for aspect in spec.unique_aspect):
            warnings.append(f"{name}：游戏过滤器无法比较暗金特效数值，保留所有数值版本。")
    if spec.inherent_pool:
        warnings.append(f"{name}：无法区分固有属性与随机词缀，已放宽固有属性条件。")
    if spec.affix_pool:
        group = spec.affix_pool[0]
        ids = _mapped([affix.name for affix in group.count], catalog, "affix")
        # Same rule as D4LF evaluation: a pool never requires more matches than it lists.
        required = min(group.min_count, len(group.count))
        if ids and 0 < required <= len(ids):
            conditions.append(Condition(ConditionKind.REQUIRED_AFFIXES, sno_ids=ids, min_count=required))
        elif not ids or required > len(ids):
            warnings.append(f"{name}：词缀 SNO 映射不完整，已放宽词缀要求。")
        if len(spec.affix_pool) > 1:
            warnings.append(f"{name}：存在多个词缀计数组；仅转换第一组，其余放宽以防误隐藏。")
        if any(
            affix.value is not None or affix.min_percent_of_affix for pool in spec.affix_pool for affix in pool.count
        ):
            warnings.append(f"{name}：词缀数值/百分比阈值无法表达，保留所有数值版本。")
        if any(affix.want_greater for pool in spec.affix_pool for affix in pool.count):
            warnings.append(f"{name}：逐词缀 GA 组合语义不完全相同，仅保留总 GA 数条件。")
    return Rule(name=name, conditions=conditions)


def compile_profile(
    profile: ProfileModel, catalog: EquipmentCatalog, policy: CompilePolicy | None = None
) -> CompilationResult:
    """Never strengthen a condition or truncate keep rules to fit the game budget."""
    policy = policy or CompilePolicy()
    warnings = [f"数据版本：{catalog.game_version}。原生导出仍需当前游戏版本导入验收。"]
    rules = [Rule("神话物品保护", conditions=[Condition(ConditionKind.RARITY, mask=32)])]
    for group in profile.affixes:
        for name, spec in group.root.items():
            rules.append(_compile_rule(name, spec, catalog, warnings))
    if policy.keep_aspects == "all":
        rules.append(Rule("保留所有传奇威能", conditions=[Condition(ConditionKind.RARITY, mask=8)]))
    elif policy.keep_aspects == "upgrade" or profile.aspect_upgrades:
        rules.append(Rule("法典升级保护", conditions=[Condition(ConditionKind.CODEX)]))
        if policy.keep_aspects != "upgrade":
            warnings.append("Build 指定威能升级无法按名称限制；保留全部法典升级。")
    if profile.global_uniques:
        for index, unique in enumerate(profile.global_uniques, 1):
            conditions = [Condition(ConditionKind.RARITY, mask=16)]
            if unique.min_power:
                conditions.append(Condition(ConditionKind.ITEM_POWER, minimum=unique.min_power))
            if unique.min_greater_affix_count:
                conditions.append(Condition(ConditionKind.GREATER_AFFIX, min_count=unique.min_greater_affix_count))
            if unique.min_percent_of_aspect:
                warnings.append(f"全局暗金规则 {index} 的特效百分比无法表达，已放宽。")
            rules.append(Rule(f"全局暗金 {index}", conditions=conditions))
    elif policy.handle_uniques != "junk":
        rules.append(Rule("未匹配暗金保护", conditions=[Condition(ConditionKind.RARITY, mask=16)]))
    if profile.charms or profile.seals or profile.tributes or profile.sigils.blacklist or profile.sigils.whitelist:
        warnings.append("护符、封印、贡品、梦魇钥匙及其他特殊分类保持显示，仍由 D4LF 原有规则处理。")
    equipment_ids = _mapped(
        [
            item_type.value
            for item_type in ItemType
            if is_weapon(item_type) or is_armor(item_type) or is_jewelry(item_type)
        ],
        catalog,
        "type",
    )
    blockers = []
    if not policy.filter_equipment:
        blockers.append("D4LF 已关闭装备过滤")
    if policy.handle_cosmetics != "junk":
        blockers.append("当前设置会保留未解锁外观，而原生协议没有外观解锁条件")
    if policy.preserve_sanctified:
        blockers.append("D4LF 会跳过圣化装备，尚无已核验的原生等价条件")
    if policy.protect_ancestral_legendaries:
        blockers.append("D4LF 已开启先祖传奇保护（不标记为垃圾），游戏过滤器没有已核验的先祖条件")
    if not equipment_ids:
        blockers.append("装备类别 SNO 映射不完整")
    if equipment_ids:
        rules.append(
            Rule(
                "隐藏其余装备文字",
                Action.HIDE_LABEL,
                enabled=not blockers,
                conditions=[Condition(ConditionKind.ITEM_TYPES, sno_ids=equipment_ids)],
            )
        )
    rules.append(Rule("显示其他物品"))
    if blockers:
        warnings.append("当前不会隐藏物品：" + "；".join(blockers) + "。可在独立编辑模式明确设置自己的隐藏规则。")
    if len(rules) > MAX_RULES:
        warnings.append(
            f"需要 {len(rules)} 条规则，超过游戏 25 条上限。已退回显示全部，未截断任何保留条件。请拆分 Profile。"
        )
        rules = [Rule("显示全部：规则数量超限")]
    document = NativeFilter(name=profile.name, rules=rules)
    return CompilationResult(
        document,
        tuple(dict.fromkeys(warnings)),
        profile.name,
        profile_digest(profile),
        catalog.game_version,
        strict=not blockers and len(warnings) == 1,
    )
