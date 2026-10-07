from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.equipment_knowledge import load_catalog
from src.game_data import ItemRarity, ItemType
from src.native_filter import Action, CompilePolicy, ConditionKind, compile_profile, encode_filter
from src.native_filter.compiler import profile_scope_warnings
from src.profiles import (
    AffixFilterCountModel,
    AffixFilterModel,
    DynamicItemFilterModel,
    GlobalUniqueModel,
    ItemFilterModel,
    ProfileModel,
)


def _profile(spec: ItemFilterModel, count: int = 1) -> ProfileModel:
    return ProfileModel.model_construct(
        name="测试 Build",
        affixes=[DynamicItemFilterModel.model_construct(root={f"规则 {index}": spec}) for index in range(count)],
    )


def test_profile_keeps_thresholds_and_uses_catalog_ids():
    affixes = [
        AffixFilterModel.model_construct(name="willpower"),
        AffixFilterModel.model_construct(name="maximum_life"),
    ]
    group = AffixFilterCountModel.model_construct(count=affixes, min_count=1, max_count=2)
    spec = ItemFilterModel.model_construct(
        item_type=[ItemType.Boots],
        min_power=731,
        min_greater_affix_count=1,
        rarities=[ItemRarity.Legendary],
        affix_pool=[group],
    )
    result = compile_profile(_profile(spec), load_catalog())
    rule = result.document.rules[1]
    by_kind = {condition.kind: condition for condition in rule.conditions}
    assert by_kind[ConditionKind.ITEM_POWER].minimum == 731
    assert by_kind[ConditionKind.ITEM_TYPES].sno_ids == (446832,)
    assert by_kind[ConditionKind.GREATER_AFFIX].min_count == 1
    assert by_kind[ConditionKind.REQUIRED_AFFIXES].min_count == 1
    assert not result.document.hides_items
    assert any("当前不会隐藏" in warning for warning in result.warnings)
    assert encode_filter(result.document)


def test_unknown_affix_broadens_instead_of_dropping_keep_rule():
    group = AffixFilterCountModel.model_construct(
        count=[AffixFilterModel.model_construct(name="unknown-future-affix")], min_count=1
    )
    spec = ItemFilterModel.model_construct(item_type=[ItemType.Boots], affix_pool=[group])
    result = compile_profile(_profile(spec), load_catalog())
    assert result.document.rules[1].conditions == [
        next(
            condition for condition in result.document.rules[1].conditions if condition.kind == ConditionKind.ITEM_TYPES
        )
    ]
    assert any("词缀 SNO" in warning for warning in result.warnings)


def test_keep_protections_and_global_unique_are_compiled():
    profile = ProfileModel.model_construct(
        name="Protections",
        global_uniques=[
            GlobalUniqueModel.model_construct(min_power=801, min_greater_affix_count=2, min_percent_of_aspect=75)
        ],
    )
    result = compile_profile(profile, load_catalog(), CompilePolicy(keep_aspects="all"))
    assert result.document.rules[0].conditions[0].mask == 32
    assert any(rule.name == "保留所有传奇威能" for rule in result.document.rules)
    unique = next(rule for rule in result.document.rules if rule.name == "全局暗金 1")
    assert (
        next(condition for condition in unique.conditions if condition.kind == ConditionKind.ITEM_POWER).minimum == 801
    )
    assert any("百分比" in warning for warning in result.warnings)


def test_rule_budget_never_truncates_protected_items():
    profile = _profile(ItemFilterModel.model_construct(min_power=123), 28)
    result = compile_profile(profile, load_catalog())
    assert len(result.document.rules) == 1
    assert result.document.rules[0].conditions == []
    assert not result.document.hides_items
    assert any("超过游戏" in warning for warning in result.warnings)


def test_generation_does_not_mutate_previous_user_document():
    profile = _profile(ItemFilterModel.model_construct(min_power=500))
    first = compile_profile(profile, load_catalog())
    first.document.rules[1].name = "我的手工修改"
    second = compile_profile(profile, load_catalog())
    assert first.document.rules[1].name == "我的手工修改"
    assert second.document.rules[1].name == "规则 0"
    assert second.profile_digest == first.profile_digest


def test_explicit_drop_policy_can_enable_hide_without_changing_global_settings():
    profile = _profile(ItemFilterModel.model_construct(item_type=[ItemType.Boots], min_power=700))
    policy = CompilePolicy(handle_cosmetics="junk", preserve_sanctified=False)
    result = compile_profile(profile, load_catalog(), policy)
    assert result.document.hides_items
    assert any(rule.action == 1 and rule.enabled for rule in result.document.rules)
    assert policy.handle_cosmetics == "junk"


def test_multiple_count_groups_relax_extra_groups_and_thresholds():
    groups = [
        AffixFilterCountModel.model_construct(
            count=[AffixFilterModel.model_construct(name=name, value=25)], min_count=1
        )
        for name in ("willpower", "maximum_life")
    ]
    result = compile_profile(_profile(ItemFilterModel.model_construct(affix_pool=groups)), load_catalog())
    assert (
        sum(condition.kind == ConditionKind.REQUIRED_AFFIXES for condition in result.document.rules[1].conditions) == 1
    )
    assert any("多个词缀" in warning for warning in result.warnings)
    assert any("数值/百分比" in warning for warning in result.warnings)


PROTECTED_PROFILE = ProfileModel.model_construct(
    name="p",
    affixes=[DynamicItemFilterModel.model_construct(root={"b": ItemFilterModel.model_construct(min_power=900)})],
)


def _general(**overrides):
    values = {
        "filter_equipment": True,
        "keep_aspects": "upgrade",
        "handle_uniques": "favorite",
        "handle_cosmetics": "ignore",
        "do_not_junk_ancestral_legendaries": False,
    }
    return SimpleNamespace(**(values | overrides))


def _hiding(rules) -> bool:
    return any(rule.action == Action.HIDE_LABEL and rule.enabled for rule in rules)


@pytest.mark.parametrize("protected", [True, False])
def test_ancestral_protection_blocks_hiding_even_with_drop_policy(protected) -> None:
    policy = CompilePolicy.from_settings(_general(do_not_junk_ancestral_legendaries=protected))
    assert policy.protect_ancestral_legendaries is protected
    drop_policy = replace(policy, handle_cosmetics="junk", preserve_sanctified=False)
    result = compile_profile(PROTECTED_PROFILE, load_catalog(), drop_policy)
    assert _hiding(result.document.rules) is not protected
    assert any("先祖传奇保护" in warning for warning in result.warnings) is protected
    # No unverified "ancestral" property bit is ever guessed.
    assert not any(c.kind == ConditionKind.PROPERTIES for r in result.document.rules for c in r.conditions)


def test_default_policy_never_hides() -> None:
    assert not _hiding(compile_profile(PROTECTED_PROFILE, load_catalog()).document.rules)


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [([], None), (["p"], None), ([" p ", ""], None), (["p", "other", "other"], "other"), (["a", "b"], "a、b")],
)
def test_profile_scope_warning_names_other_enabled_profiles(enabled, expected) -> None:
    warnings = profile_scope_warnings("p", enabled)
    assert bool(warnings) is (expected is not None)
    if expected:
        assert f"只编译所选 Profile「p」；D4LF 还启用了 {expected}" in warnings[0]


def test_legacy_oversized_pool_compiles_to_all_listed_affixes() -> None:
    group = AffixFilterCountModel.model_construct(
        count=[
            AffixFilterModel.model_construct(name="willpower"),
            AffixFilterModel.model_construct(name="maximum_life"),
        ],
        min_count=3,
    )
    result = compile_profile(_profile(ItemFilterModel.model_construct(affix_pool=[group])), load_catalog())
    required = [c for c in result.document.rules[1].conditions if c.kind == ConditionKind.REQUIRED_AFFIXES]
    assert [condition.min_count for condition in required] == [2]
