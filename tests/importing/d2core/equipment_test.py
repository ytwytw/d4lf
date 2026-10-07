from dataclasses import replace
from typing import TYPE_CHECKING, cast

import pytest

from src.game_data import WEAPON_TYPES, GameCatalog, ItemRarity, ItemType
from src.importing.d2core.catalog import CatalogStore, CatalogTransport
from src.importing.d2core.equipment import _canonical_aspect_name, _item_type, normalize_variant
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.rules import EvaluationSettings, LoadedRules
from src.profiles import DynamicItemFilterModel, ItemFilterModel
from src.settings import AspectFilterType

if TYPE_CHECKING:
    from src.type_aliases import JsonObject


def test_equipment_type_uses_safe_slot_fallbacks() -> None:
    assert _item_type("", slot="0", class_name="Druid") is ItemType.Helm
    assert _item_type("weapon", slot="5", class_name="Druid") == WEAPON_TYPES
    assert _item_type("unknown", slot="99", class_name="Druid") is None
    assert _item_type("unknown", slot="12", class_name="Druid") is ItemType.OffHandTotem


def test_aspect_catalog_matcher_preserves_catalog_entry() -> None:
    aspect_name = GameCatalog().aspect_list[0]

    assert _canonical_aspect_name({"name": aspect_name.title()}) == aspect_name


def test_unique_equipment_type_comes_from_joined_catalog_not_payload_label() -> None:
    unique_name, unique_label = next(iter(GameCatalog().aspect_unique_dict.items()))
    catalogs = CatalogStore(
        version="v1",
        transport=CatalogTransport(),
        data=cast(
            "dict[str, JsonObject]",
            cast(
                "object",
                {
                    "affix": {"affix": {}},
                    "uniqueItem": {
                        "uniqueItem": {
                            "unique-key": {"key": "unique-key", "name": unique_label, "equipTypeName": "Ring"}
                        }
                    },
                },
            ),
        ),
    )
    variant = normalize_variant(
        {"gear": {"0": {"type": "uniqueItem", "key": "unique-key", "itemType": "Helm", "mods": []}}},
        variant_name="Variant 1",
        class_name="Druid",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_aspect_upgrades=False,
        warn=lambda *_args: None,
    )

    assert variant.affix_filters[0].item_type == [ItemType.Ring]
    assert variant.affix_filters[0].unique_aspect[0].name == unique_name


def test_current_d2core_catalog_schema_preserves_english_helm_stats() -> None:
    catalogs = CatalogStore(
        version="v1",
        transport=CatalogTransport(),
        data={
            "affix": {
                "affix": {
                    "S04_CoreStat_Willpower": {"key": "S04_CoreStat_Willpower", "desc": "+[100 - 121] Willpower"},
                    "S04_Life": {"key": "S04_Life", "desc": "+[1,226 - 1,450] Maximum Life"},
                    "S04_Resistance_All": {
                        "key": "S04_Resistance_All",
                        "desc": "+[327 - 392] Resistance to All Elements",
                    },
                    "S04_ResourceGain": {"key": "S04_ResourceGain", "desc": "[11.0 - 15.0]% Resource Generation"},
                    "Tempered_Generic_LifeMax_Tier3": {
                        "key": "Tempered_Generic_LifeMax_Tier3",
                        "desc": "+[1,000 - 1,500] Maximum Life",
                    },
                }
            },
            "uniqueItem": {
                "uniqueItem": {
                    "Helm_Unique_Druid_102": {
                        "key": "Helm_Unique_Druid_102",
                        "name": "Gathlen's Birthright",
                        "equipTypeName": "Helm",
                    }
                }
            },
        },
    )

    variant = normalize_variant(
        {
            "gear": {
                "0": {
                    "type": "uniqueItem",
                    "key": "Helm_Unique_Druid_102",
                    "itemType": "Helm",
                    "mods": [
                        {"name": "S04_CoreStat_Willpower"},
                        {"name": "S04_Life"},
                        {"name": "S04_Resistance_All"},
                        {"name": "S04_ResourceGain"},
                        {"name": "Tempered_Generic_LifeMax_Tier3", "greater": True},
                    ],
                }
            }
        },
        variant_name="Variant 1",
        class_name="Druid",
        catalogs=catalogs,
        import_greater_affixes=True,
        require_greater_affixes=False,
        import_aspect_upgrades=False,
        warn=lambda *_args: None,
    )

    helm = variant.affix_filters[0]
    assert [affix.name for affix in helm.affix_pool[0].count] == [
        "willpower",
        "maximum_life",
        "resistance_to_all_elements",
        "resource_generation",
        "maximum_life",
    ]
    assert [affix.want_greater for affix in helm.affix_pool[0].count] == [False, False, False, False, True]


def test_non_unique_item_keeps_safe_type_when_all_affix_joins_fail() -> None:
    catalogs = CatalogStore(version="v1", transport=CatalogTransport(), data={"affix": {"affix": {}}})
    variant = normalize_variant(
        {"gear": {"0": {"type": "rare", "itemType": "Helm", "mods": [{"name": "unknown-affix"}]}}},
        variant_name="Variant 1",
        class_name="Druid",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_aspect_upgrades=False,
        warn=lambda *_args: None,
    )

    assert variant.affix_filters[0].item_type == [ItemType.Helm]
    assert not variant.affix_filters[0].affix_pool


def test_missing_aspect_join_uses_optional_warning_code() -> None:
    catalogs = CatalogStore(
        version="v1", transport=CatalogTransport(), data={"affix": {"affix": {}}, "aspect": {"aspect": {}}}
    )
    warnings: list[tuple[str, str, str, str]] = []

    variant = normalize_variant(
        {"gear": {"0": {"type": "legendary", "itemType": "Helm", "key": "missing-aspect", "mods": []}}},
        variant_name="Variant 1",
        class_name="Druid",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_aspect_upgrades=True,
        warn=lambda *warning: warnings.append(warning),
    )

    assert variant.aspect_upgrade_filters == []
    assert warnings == [("D2C-W120", "Variant 1", "aspect", "missing-aspect")]


D2CORE_AFFIXES = {
    "S04_CoreStat_Willpower": {"key": "S04_CoreStat_Willpower", "desc": "+[100 - 121] Willpower"},
    "S04_Life": {"key": "S04_Life", "desc": "+[1,226 - 1,450] Maximum Life"},
    "S04_Resistance_All": {"key": "S04_Resistance_All", "desc": "+[327 - 392] Resistance to All Elements"},
    "S04_ResourceGain": {"key": "S04_ResourceGain", "desc": "[11.0 - 15.0]% Resource Generation"},
}


def _keeps(spec: ItemFilterModel, affixes: list[str]) -> bool:
    rules = replace(LoadedRules.empty(), affix_filters={"p": [DynamicItemFilterModel(root={"helm": spec})]})
    evaluator = FilterEvaluator(rules=rules, evaluation_settings=EvaluationSettings(keep_aspects=AspectFilterType.none))
    affix_models = [Affix(name=name) for name in affixes]
    return evaluator.should_keep(
        Item(item_type=ItemType.Helm, rarity=ItemRarity.Legendary, power=800, affixes=affix_models)
    ).keep


def _d2core_helm(mods: list[str], warnings: list[tuple[str, ...]]) -> ItemFilterModel:
    catalogs = CatalogStore(version="v1", transport=CatalogTransport(), data={"affix": {"affix": D2CORE_AFFIXES}})
    variant = normalize_variant(
        {"gear": {"0": {"type": "legendaryItem", "itemType": "Helm", "mods": [{"name": mod} for mod in mods]}}},
        variant_name="Variant 1",
        class_name="Druid",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_aspect_upgrades=False,
        warn=lambda *args: warnings.append(args),
    )
    return variant.affix_filters[0]


def test_unresolved_mods_relax_the_pool_so_source_matches_are_kept() -> None:
    warnings: list[tuple[str, ...]] = []
    spec = _d2core_helm(["S04_CoreStat_Willpower", "S04_Life", "Unknown_A", "Unknown_B"], warnings)
    assert [affix.name for affix in spec.affix_pool[0].count] == ["willpower", "maximum_life"]
    assert spec.affix_pool[0].min_count == 1
    assert len(warnings) == 2
    # The source asked for 3 of 4; life plus both unreadable mods met that rule.
    assert _keeps(spec, ["maximum_life", "strength"])
    assert not _keeps(spec, ["strength", "armor"])


def test_complete_mods_keep_the_three_affix_requirement() -> None:
    spec = _d2core_helm(list(D2CORE_AFFIXES), [])
    assert spec.affix_pool[0].min_count == 3
    assert not _keeps(spec, ["willpower", "maximum_life"])
    assert _keeps(spec, ["willpower", "maximum_life", "resource_generation"])


@pytest.mark.parametrize("mods", [["S04_Life", "Unknown_A", "Unknown_B", "Unknown_C"], ["Unknown_A", "Unknown_B"]])
def test_unresolved_mods_that_could_meet_the_rule_broaden_the_slot(mods) -> None:
    spec = _d2core_helm(mods, [])
    assert spec.item_type == [ItemType.Helm]
    assert spec.affix_pool == []
    # The source rule may be met by the unreadable mods alone, so no imported affix may be required.
    assert _keeps(spec, ["strength"])


def test_relaxed_pool_still_requires_what_the_source_rule_implies() -> None:
    spec = _d2core_helm(["S04_Life", "Unknown_A", "Unknown_B"], [])  # all 3 required, 2 unreadable
    assert spec.affix_pool[0].min_count == 1
    assert _keeps(spec, ["maximum_life"])
    assert not _keeps(spec, ["strength"])


def test_unmappable_unique_or_item_type_marks_the_variant_unsafe() -> None:
    catalogs = CatalogStore(version="v1", transport=CatalogTransport(), data={"affix": {"affix": D2CORE_AFFIXES}})
    gear = {
        "0": {"type": "uniqueItem", "key": "Future_Unique", "mods": [{"name": "S04_Life"}]},
        "99": {"type": "legendaryItem", "itemType": "Mystery", "mods": [{"name": "S04_Life"}]},
    }
    variant = normalize_variant(
        {"gear": gear},
        variant_name="Variant 1",
        class_name="Druid",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_aspect_upgrades=False,
        warn=lambda *_args: None,
    )
    assert variant.affix_filters == []
    assert variant.unsafe_slots == ["slot 0 unique Future_Unique", "slot 99 item type Mystery"]
