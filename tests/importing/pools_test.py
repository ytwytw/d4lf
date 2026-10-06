"""Imported pools keep every item that met the source rule, and stay exact when every affix was imported."""

import itertools
import logging
from dataclasses import replace

import pytest

from src.game_data import ItemRarity, ItemType
from src.importing.pools import REQUIRED_EQUIPMENT_AFFIXES, import_pool, required_known_affixes
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.rules import EvaluationSettings, LoadedRules
from src.profiles import DynamicItemFilterModel, ItemFilterModel
from src.settings import AspectFilterType

NAMES = ["willpower", "maximum_life", "armor", "strength", "dexterity"]


def _keeps(pool, present: tuple[str, ...]) -> bool:
    spec = ItemFilterModel(item_type=[ItemType.Helm], affix_pool=pool)
    rules = replace(LoadedRules.empty(), affix_filters={"p": [DynamicItemFilterModel(root={"helm": spec})]})
    evaluator = FilterEvaluator(rules=rules, evaluation_settings=EvaluationSettings(keep_aspects=AspectFilterType.none))
    item = Item(
        item_type=ItemType.Helm, rarity=ItemRarity.Legendary, power=800, affixes=[Affix(name=n) for n in present]
    )
    return evaluator.should_keep(item).keep


@pytest.mark.parametrize(
    ("required", "resolved", "unresolved", "expected"),
    [(3, 4, 0, 3), (3, 2, 0, 2), (3, 3, 1, 2), (3, 2, 2, 1), (3, 1, 2, 1), (3, 1, 3, 0), (3, 0, 4, 0), (1, 2, 1, 0)]
    + [(1, 3, 0, 1)],
)
def test_required_known_affixes(required, resolved, unresolved, expected) -> None:
    assert required_known_affixes(required, resolved, unresolved) == expected


@pytest.mark.parametrize("listed", [1, 2, 3, 4, 5])
def test_every_item_meeting_the_source_rule_is_kept_and_complete_imports_stay_exact(listed) -> None:
    names = NAMES[:listed]
    source_required = min(REQUIRED_EQUIPMENT_AFFIXES, listed)
    for unresolved in range(listed + 1):
        resolved = [Affix(name=name) for name in names[: listed - unresolved]]
        pool = import_pool(resolved, REQUIRED_EQUIPMENT_AFFIXES, unresolved)
        for size in range(listed + 1):
            for present in itertools.combinations(names, size):
                met_source_rule = len(present) >= source_required
                kept = _keeps(pool, present)
                assert kept or not met_source_rule, (unresolved, present)
                if unresolved == 0:
                    assert kept == met_source_rule, present


def test_broadened_and_relaxed_pools_warn_in_english_and_chinese(caplog) -> None:
    affix = [Affix(name="willpower")]
    with caplog.at_level(logging.WARNING, logger="src.importing.pools"):
        assert import_pool(affix, 3, 3, context="Slot A") == []
        assert import_pool(affix * 1 + [Affix(name="armor")], 3, 2, context="Slot B")[0].min_count == 1
        assert import_pool(affix, 3, 0, context="Slot C")[0].min_count == 1
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert "Slot A: 3 source affix(es) could not be imported, so no imported affix is required" in messages[0]
    assert "此规则现在保留其他条件匹配的所有物品" in messages[0]
    assert "requiring 1 of the 2 imported affixes" in messages[1]
    assert "改为要求 2 个已导入词缀中的 1 个" in messages[1]
