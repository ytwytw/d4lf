from dataclasses import replace
from typing import TYPE_CHECKING, cast

import pytest

from src.game_data import ItemRarity, ItemType
from src.importing import ImportRequest
from src.importing.mobalytics import filters
from src.importing.mobalytics.filters import _resolve_item_type
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.rules import LoadedRules
from src.profiles import DynamicItemFilterModel

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

    from src.importing.pipeline import Variant
    from src.type_aliases import JsonObject


def test_mobalytics_filter_type_resolution_handles_missing_values() -> None:
    assert _resolve_item_type([], "", "") is None


@pytest.mark.parametrize("name", ["Doombringer", "Grief"])
def test_build_variant_normalizes_unique_weapon_slot_suffix(mock_ini_loader, monkeypatch, name: str) -> None:
    monkeypatch.setattr(filters, "_get_weapon_type_from_slot_tooltip", lambda **_kwargs: None)
    variant = filters.build_variant(
        items=[
            {
                "gameEntity": {"type": "uniqueItems", "entity": {"title": f"{name} (1h Sword)"}},
                "gameSlotSlug": "dual-wield-weapon-1",
            }
        ],
        class_name="Rogue",
        request=ImportRequest(url="https://example.invalid/build"),
        driver=cast("WebDriver", object()),
        variant_name="",
        build_name="",
        paragon_data={},
        error_type=ValueError,
    )

    assert len(variant.affix_filters) == 1
    assert variant.affix_filters[0].unique_aspect[0].name == name.lower()
    assert variant.affix_filters[0].item_type == [ItemType.Sword]


def _variant(items) -> Variant:
    return filters.build_variant(
        items=items,
        class_name="Rogue",
        request=ImportRequest(url="https://example.invalid/build"),
        driver=cast("WebDriver", object()),
        variant_name="Pit",
        build_name="",
        paragon_data={},
        error_type=ValueError,
    )


def _entry(entity_type: str, title: str, slot: str, stats: list[JsonObject]) -> JsonObject:
    stat_key = "charmStats" if "charm" in slot else "gearStats"
    return {"gameEntity": {"type": entity_type, "title": title, "modifiers": {stat_key: stats}}, "gameSlotSlug": slot}


@pytest.mark.parametrize(("missing", "min_counts"), [(3, []), (1, [2])])
def test_unreadable_stats_relax_or_broaden_the_slot(mock_ini_loader, missing, min_counts) -> None:
    stats = [{"id": "maximum-life"}, {"id": "armor"}] + [{"value": 1}] * missing
    variant = _variant([_entry("items", "Helm", "helm", stats)])
    (rule,) = variant.affix_filters
    assert [group.min_count for group in rule.affix_pool] == min_counts
    rules = replace(LoadedRules.empty(), affix_filters={"p": [DynamicItemFilterModel(root={"helm": rule})]})
    item = Item(item_type=ItemType.Helm, rarity=ItemRarity.Legendary, power=800, affixes=[Affix(name="strength")])
    assert FilterEvaluator(rules).should_keep(item).keep is (not min_counts)


def test_unreadable_charm_stat_keeps_the_charm_broadly(mock_ini_loader) -> None:
    variant = _variant([_entry("charms", "Rare Charm", "charm-1", [{"id": "maximum-life"}, {"value": 1}])])
    assert [charm.affix_pool for charm in variant.charm_filters] == [[]]
    assert variant.unsafe_slots == []


def test_unknown_unique_or_untitled_entry_is_unsafe(mock_ini_loader) -> None:
    variant = _variant([_entry("uniqueItems", "Future Unique", "helm", []), _entry("items", "", "boots", [])])
    assert variant.affix_filters == []
    assert variant.unsafe_slots == ["helm unique Future Unique", "boots items (no title)"]
