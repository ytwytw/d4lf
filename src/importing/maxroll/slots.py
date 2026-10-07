"""Turn one Maxroll planner item into a loot rule without silently dropping a wanted slot.

Unreadable affixes relax or broaden the slot rule (see ``src.importing.pools``). Item identities that no rule can
represent (runewords, unknown uniques, unknown item types) are recorded as unsafe so the import is rejected
before any profile is written.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from src.game_data import GameCatalog, ItemRarity, ItemType
from src.importing.filters import (
    create_item_affix_pool,
    create_seal_charm_filter,
    is_unique_like_rarity,
    resolve_unique_name,
    update_mingreateraffixcount,
)
from src.importing.maxroll.data import _find_item_name, _has_explicit_affix_references
from src.importing.maxroll.items import _find_item_affixes, _find_item_rarity
from src.importing.maxroll.planner import _find_item_type, _find_legendary_aspect, _unique_name_special_handling
from src.importing.pools import REQUIRED_EQUIPMENT_AFFIXES
from src.perception import correct_name
from src.profiles import AspectUniqueFilterModel, CharmFilterModel, ItemFilterModel, SealFilterModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from src.importing.contracts import ImportRequest
    from src.type_aliases import JsonObject, JsonValue

LOGGER = logging.getLogger(__name__)


@dataclass
class VariantSlots:
    affix_filters: list[ItemFilterModel] = field(default_factory=list)
    charm_filters: list[CharmFilterModel] = field(default_factory=list)
    seal_filters: list[SealFilterModel] = field(default_factory=list)
    aspect_upgrade_filters: list[str] = field(default_factory=list)
    unsafe: list[str] = field(default_factory=list)
    unsafe_charms: list[str] = field(default_factory=list)
    unsafe_seals: list[str] = field(default_factory=list)


def _set_name(item_id: str, mapping_data: JsonObject) -> str | None:
    item_mapping = cast("Mapping[str, Mapping[str, JsonValue]]", mapping_data["items"])
    item_sets = cast("Mapping[str, Mapping[str, JsonValue]]", mapping_data.get("itemSets", {}))
    set_record = item_sets.get(str(item_mapping.get(item_id, {}).get("set")), {})
    set_name = correct_name(str(set_record.get("name", "")))
    if set_name in GameCatalog().set_list:
        return set_name
    LOGGER.warning("Unknown Maxroll charm set for %s; keeping the charm without a set requirement.", item_id)
    return None


def add_item(
    slots: VariantSlots,
    resolved_item: JsonObject,
    *,
    mapping_data: JsonObject,
    class_name: str,
    variant_name: str,
    request: ImportRequest,
) -> None:
    item_id = str(resolved_item["id"])
    item_mapping = cast("dict[str, JsonObject]", mapping_data["items"])
    item_type = _find_item_type(
        mapping_data=cast("Mapping[str, Mapping[str, str]]", item_mapping), value=item_id, class_name=class_name
    )
    if item_type is None:
        LOGGER.warning(f"Couldn't find item type for {item_id} from mapping data provided by Maxroll.")
        slots.unsafe.append(f"item {item_id} (unknown item type)")
        return
    item_name = _find_item_name(resolved_item=resolved_item, resolved_item_id=item_id, item_mapping=item_mapping)
    rarity = _find_item_rarity(item_id, mapping_data)
    # Runewords drop as named unique items (for example Enigma), independent of the planner's rarity mapping.
    is_runeword = item_id.startswith("Runeword_")
    unique_aspect = None
    if is_runeword or is_unique_like_rarity(rarity):
        candidate = correct_name(_unique_name_special_handling(item_name or "")) or ""
        canonical = candidate if candidate in GameCatalog().aspect_unique_dict else resolve_unique_name(item_name or "")
        if canonical:
            unique_aspect = AspectUniqueFilterModel(name=canonical)
        else:
            kind = "runeword" if is_runeword else "unique"
            LOGGER.warning("Maxroll %s %s (%s) is not in D4LF's item data.", kind, item_name, item_id)
            category = {ItemType.Charm: slots.unsafe_charms, ItemType.HoradricSeal: slots.unsafe_seals}
            category.get(item_type, slots.unsafe).append(f"{kind} {item_name or item_id}")
            return

    unresolved: list[str] = []
    if explicits_known := _has_explicit_affix_references(resolved_item):
        affixes = _find_item_affixes(
            mapping_data=mapping_data,
            item_affixes=cast("list[JsonObject]", resolved_item["explicits"]),
            item_type=item_type,
            import_greater_affixes=request.options.import_greater_affixes,
            unresolved=unresolved,
        )
    else:
        LOGGER.warning("Maxroll item %s has missing or malformed explicits; keeping its slot broadly.", item_id)
        affixes = []
    unresolved_count = len(unresolved) if explicits_known else REQUIRED_EQUIPMENT_AFFIXES
    label = f"Maxroll {variant_name or 'default'} {item_name or item_id}"

    if item_type in [ItemType.HoradricSeal, ItemType.Charm]:
        set_name = _set_name(item_id, mapping_data) if unique_aspect is None and rarity == ItemRarity.Set else None
        listed_set = unique_aspect is None and rarity == ItemRarity.Set
        if not affixes and unique_aspect is None and not listed_set and not unresolved_count:
            LOGGER.warning(f"Skipping {label} because it had no supported affixes, unique aspect, or set name.")
            return
        model_type = CharmFilterModel if item_type == ItemType.Charm else SealFilterModel
        talisman = create_seal_charm_filter(
            affixes=affixes,
            require_gas=request.options.require_greater_affixes,
            model_type=model_type,
            unique_name=unique_aspect.name if unique_aspect else None,
            set_name=set_name,
            unresolved_count=unresolved_count,
        )
        if isinstance(talisman, CharmFilterModel):
            slots.charm_filters.append(talisman)
        else:
            slots.seal_filters.append(talisman)
        return

    item_filter = ItemFilterModel()
    item_filter.item_type = [item_type]
    if rarity == ItemRarity.Legendary and request.options.import_aspect_upgrades:
        legendary_aspect = _find_legendary_aspect(
            mapping_data,
            cast("JsonObject | list[JsonValue]", resolved_item.get("legendaryPower", resolved_item.get("aspects", {}))),
        )
        if legendary_aspect and legendary_aspect not in GameCatalog().aspect_list:
            LOGGER.warning(
                f"Found legendary aspect '{legendary_aspect}' that is not in our aspect data, unable to add "
                f"to AspectUpgrades. Please report a bug."
            )
        elif legendary_aspect:
            slots.aspect_upgrade_filters.append(legendary_aspect)
    if unique_aspect is not None:
        item_filter.unique_aspect = [unique_aspect]
    if not affixes and not unique_aspect and not unresolved_count:
        LOGGER.warning(f"Skipping {label} because it had no supported affixes or unique aspect.")
        return
    item_filter.affix_pool = create_item_affix_pool(
        affixes, unique_like=unique_aspect is not None, unresolved_count=unresolved_count, context=label
    )
    update_mingreateraffixcount(item_filter, request.options.require_greater_affixes)
    item_filter.min_power = 100
    slots.affix_filters.append(item_filter)
