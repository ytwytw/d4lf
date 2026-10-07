"""Maxroll slots: unreadable affixes relax or broaden the rule; unrepresentable identities reject the import."""

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from src.game_data import ItemRarity, ItemType
from src.importing import ImportOptions, ImportRequest
from src.importing.maxroll.slots import VariantSlots, add_item
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.rules import EvaluationSettings, LoadedRules
from src.profiles import DynamicItemFilterModel, DynamicSealFilterModel
from src.settings import AspectFilterType

if TYPE_CHECKING:
    from src.type_aliases import JsonObject

SHOCK = {"id": 1, "magicType": 0, "attributes": [{"id": 1155, "param": 1, "formula": "GearAffix_SkillRankBonus_1to2"}]}
WRATH = {
    "id": 2,
    "magicType": 1,
    "attributes": [{"id": 2, "param": 10, "formula": "GearAffix_ResourceMax"}],
    "desc": "{c_set}Chains of Horazon{/c}:\r\n+{c_number}[Resource_Max_Percent_Bonus(10)*100|%|]{/c} Maximum Wrath",
}


def _mapping(item_type: str, magic_type: int, name: str = "Test Item") -> JsonObject:
    return {
        "items": {"item": {"type": item_type, "magicType": magic_type, "name": name}},
        "affixes": {
            "X2_SkillRankBonus_Sorc_Category_Shock": SHOCK,
            "Talisman_SealAffix_Set_Warlock_05_MaximumWrath": WRATH,
        },
        "skills": {},
    }


def _add(item_type: str, nids: list[int], magic_type: int = 1, name: str = "Test Item") -> VariantSlots:
    slots = VariantSlots()
    add_item(
        slots,
        {"id": "item", "explicits": [{"nid": nid} for nid in nids]},
        mapping_data=_mapping(item_type, magic_type, name),
        class_name="Sorcerer",
        variant_name="Pit",
        request=ImportRequest(url="https://maxroll.gg/d4/planner/x#1", options=ImportOptions()),
    )
    return slots


def _keeps(rules: LoadedRules, item: Item) -> bool:
    return FilterEvaluator(rules, EvaluationSettings(keep_aspects=AspectFilterType.none)).should_keep(item).keep


@pytest.mark.parametrize(("nids", "min_counts"), [([1, 7, 8, 9], []), ([7, 8], []), ([1, 7, 8], [1]), ([1], [1])])
def test_unreadable_explicits_relax_or_broaden_the_equipment_rule(nids, min_counts) -> None:
    slots = _add("Amulet", nids)
    assert slots.unsafe == []
    (rule,) = slots.affix_filters
    assert [group.min_count for group in rule.affix_pool] == min_counts
    rules = replace(LoadedRules.empty(), affix_filters={"p": [DynamicItemFilterModel(root={"amulet": rule})]})
    other = Item(item_type=ItemType.Amulet, rarity=ItemRarity.Legendary, power=800, affixes=[Affix(name="armor")])
    assert _keeps(rules, other) is (not min_counts)  # broad rules keep items carrying only unreadable affixes


def test_unreadable_seal_affix_keeps_the_seal_broadly() -> None:
    slots = _add("HoradricSeal", [1, 7])
    (seal,) = slots.seal_filters
    assert seal.affix_pool == []
    rules = replace(LoadedRules.empty(), seal_filters={"p": [DynamicSealFilterModel(root={"seal": seal})]})
    item = Item(item_type=ItemType.HoradricSeal, rarity=ItemRarity.Rare, power=800, affixes=[Affix(name="armor")])
    assert _keeps(rules, item)


@pytest.mark.parametrize(
    ("item_id_type", "magic_type", "category"),
    [
        ("Helm", 2, "unsafe"),
        ("Charm", 4, "unsafe_charms"),
        ("HoradricSeal", 2, "unsafe_seals"),
        ("Mystery", 1, "unsafe"),
    ],
)
def test_unrepresentable_identity_is_recorded_as_unsafe_in_its_category(item_id_type, magic_type, category) -> None:
    slots = _add(item_id_type, [1], magic_type=magic_type, name="Unconfirmed Future Unique")
    assert slots.affix_filters == slots.charm_filters == slots.seal_filters == []
    assert {name: len(getattr(slots, name)) for name in ("unsafe", "unsafe_charms", "unsafe_seals")}[category] == 1
    assert len(slots.unsafe) + len(slots.unsafe_charms) + len(slots.unsafe_seals) == 1


def test_set_seal_affix_keeps_the_identity_maxroll_describes() -> None:
    (seal,) = _add("HoradricSeal", [2]).seal_filters
    assert [affix.name for affix in seal.affix_pool[0].count] == ["chains_of_horazon_maximum_wrath"]  # was charm_slot
    rules = replace(LoadedRules.empty(), seal_filters={"p": [DynamicSealFilterModel(root={"seal": seal})]})
    wrath, slot = (
        Item(item_type=ItemType.HoradricSeal, rarity=ItemRarity.Rare, power=800, affixes=[Affix(name=name)])
        for name in ("chains_of_horazon_maximum_wrath", "charm_slot")
    )
    assert _keeps(rules, wrath)
    assert not _keeps(rules, slot)
