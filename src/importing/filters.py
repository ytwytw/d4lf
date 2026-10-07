import logging
from enum import Enum
from typing import TYPE_CHECKING, TypeVar, overload

from src.game_data import WEAPON_TYPES, GameCatalog, ItemRarity, ItemType
from src.importing.pools import REQUIRED_EQUIPMENT_AFFIXES, import_pool
from src.item import Affix, AffixType
from src.profiles import (
    AffixFilterCountModel,
    AspectUniqueFilterModel,
    CharmFilterModel,
    ItemFilterModel,
    SealFilterModel,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


E = TypeVar("E", bound=Enum)
FilterModelT = TypeVar("FilterModelT", bound=ItemFilterModel | CharmFilterModel | SealFilterModel)
LOGGER = logging.getLogger(__name__)


def fix_weapon_type(input_str: str) -> ItemType | None:
    input_str = input_str.lower()
    weapon_types = {
        "1h axe": ItemType.Axe,
        "1h mace": ItemType.Mace,
        "1h sword": ItemType.Sword,
        "2h axe": ItemType.Axe2H,
        "2h mace": ItemType.Mace2H,
        "2h scythe": ItemType.Scythe2H,
        "2h sword": ItemType.Sword2H,
        "crossbow": ItemType.Crossbow2H,
        "bow": ItemType.Bow,
        "dagger": ItemType.Dagger,
        "flail": ItemType.Flail,
        "glaive": ItemType.Glaive,
        "polearm": ItemType.Polearm,
        "quarterstaff": ItemType.Quarterstaff,
        "scythe": ItemType.Scythe,
        "staff": ItemType.Staff,
        "wand": ItemType.Wand,
    }
    for name, item_type in weapon_types.items():
        if name in input_str:
            return item_type
    return None


def fix_offhand_type(input_str: str, class_str: str) -> ItemType | None:
    input_str, class_str = input_str.lower(), class_str.lower()
    if "sorc" in class_str or "warlock" in class_str:
        return ItemType.Focus
    if "druid" in class_str:
        return ItemType.OffHandTotem
    if "paladin" in class_str:
        return ItemType.Shield
    if "necro" in class_str:
        if "focus" in input_str:
            return ItemType.Focus
        if "shield" in input_str:
            return ItemType.Shield
    return None


PLAYER_CLASSES = ["barbarian", "druid", "necromancer", "rogue", "sorcerer", "spiritborn", "paladin", "warlock"]


def get_class_name(input_str: str) -> str:
    for class_name in PLAYER_CLASSES:
        if class_name in input_str.lower():
            return class_name.title()
    LOGGER.error(f"Couldn't match class name {input_str=}")
    return "Unknown"


def update_mingreateraffixcount(item_filter: ItemFilterModel, require_gas: bool) -> None:
    # A broadened rule has no pool and so no greater-affix requirement either.
    pool = item_filter.affix_pool[0].count if item_filter.affix_pool else []
    item_filter.min_greater_affix_count = sum(affix.want_greater for affix in pool) if require_gas else 0


def resolve_unique_name(label: str) -> str | None:
    """Canonical unique id for a source label (as the profile model normalizes it, then catalog aliases)."""
    normalized = label.lower().replace("'", "").replace(" ", "_").replace(",", "")
    if normalized in GameCatalog().aspect_unique_dict:
        return normalized
    return GameCatalog().resolve_unique(label) if label.strip() else None


def is_unique_like_rarity(rarity: ItemRarity | str | None) -> bool:
    if isinstance(rarity, ItemRarity):
        return rarity in (ItemRarity.Unique, ItemRarity.Mythic)
    return str(rarity).strip().casefold() in {"unique", "mythic"}


def create_item_affix_pool(
    affixes: list[Affix], unique_like: bool, *, unresolved_count: int = 0, context: str = ""
) -> list[AffixFilterCountModel]:
    """Pool for an imported equipment slot; see ``import_pool`` for how unresolved affixes relax it."""
    required = 1 if unique_like else REQUIRED_EQUIPMENT_AFFIXES
    return import_pool(affixes, required, unresolved_count, context=context)


@overload
def create_seal_charm_filter(
    affixes: list[Affix],
    require_gas: bool,
    model_type: type[SealFilterModel] = SealFilterModel,
    unique_name: str | None = None,
    set_name: str | None = None,
    *,
    unresolved_count: int = 0,
) -> SealFilterModel: ...


@overload
def create_seal_charm_filter(
    affixes: list[Affix],
    require_gas: bool,
    model_type: type[CharmFilterModel],
    unique_name: str | None = None,
    set_name: str | None = None,
    *,
    unresolved_count: int = 0,
) -> CharmFilterModel: ...


@overload
def create_seal_charm_filter(
    affixes: list[Affix],
    require_gas: bool,
    model_type: type[SealFilterModel | CharmFilterModel],
    unique_name: str | None = None,
    set_name: str | None = None,
    *,
    unresolved_count: int = 0,
) -> SealFilterModel | CharmFilterModel: ...


def create_seal_charm_filter(
    affixes: list[Affix],
    require_gas: bool,
    model_type: type[SealFilterModel | CharmFilterModel] = SealFilterModel,
    unique_name: str | None = None,
    set_name: str | None = None,
    *,
    unresolved_count: int = 0,
) -> SealFilterModel | CharmFilterModel:
    # Seals and charms keep a talisman with any one listed affix, so a single unresolved affix leaves no
    # imported affix that may be required; the filter then relies on its other conditions only.
    context = unique_name or set_name or model_type.__name__.removesuffix("FilterModel")
    affix_pool = import_pool(affixes, 1, unresolved_count, context=context)
    result = (
        CharmFilterModel(set=[set_name] if set_name else []) if model_type is CharmFilterModel else SealFilterModel()
    )
    result.affix_pool = affix_pool
    result.unique_aspect = [AspectUniqueFilterModel(name=unique_name)] if unique_name else []
    if require_gas:
        result.min_greater_affix_count = sum(a.type == AffixType.greater for a in affixes)
    return result


def weapon_slot_name_hint(item_filter: ItemFilterModel, slot: str) -> str | None:
    """Name hint kept only while the weapon's item type is still unresolved."""
    return slot if item_filter.item_type == WEAPON_TYPES else None


def unique_filter_name[FilterT](filter_name_template: str, filters: Sequence[Mapping[str, FilterT]]) -> str:
    filter_name, i = filter_name_template, 2
    while any(filter_name == next(iter(existing_filter)) for existing_filter in filters):
        filter_name, i = f"{filter_name_template}{i}", i + 1
    return filter_name


def deduplicate_filters(
    filters: Sequence[FilterModelT], name_hints: Sequence[str | None] | None = None
) -> list[dict[str, FilterModelT]]:
    """Merge identical filters, naming duplicates with an (xN) count suffix."""
    if not filters:
        return []
    groups: list[tuple[str, FilterModelT, int]] = []
    for i, filter_spec in enumerate(filters):
        for idx, (base_name, existing_model, count) in enumerate(groups):
            if filter_spec == existing_model:
                groups[idx] = (base_name, existing_model, count + 1)
                break
        else:
            if isinstance(filter_spec, ItemFilterModel):
                hint = name_hints[i] if name_hints else None
                base_name = (
                    hint
                    if hint and filter_spec.item_type == WEAPON_TYPES
                    else (filter_spec.item_type[0].name if filter_spec.item_type else "Item")
                )
            else:
                base_name = "Charm" if isinstance(filter_spec, CharmFilterModel) else "HoradricSeal"
            groups.append((base_name, filter_spec, 1))
    result: list[dict[str, FilterModelT]] = []
    used_names: list[dict[str, FilterModelT]] = []
    for base_name, model, count in groups:
        key = f"{base_name}(x{count})" if count > 1 else unique_filter_name(base_name, used_names)
        suffix = 2
        while count > 1 and any(key == next(iter(existing)) for existing in used_names):
            key, suffix = f"{base_name}{suffix}(x{count})", suffix + 1
        result.append({key: model})
        used_names.append({key: model})
    return result


def sort_profile_filters(filters: Sequence[Mapping[str, FilterModelT]]) -> list[dict[str, FilterModelT]]:
    return [dict(entry) for entry in sorted(filters, key=lambda entry: next(iter(entry)).casefold())]


def match_to_enum(enum_class: type[E], target_string: str, check_keys: bool = False) -> E | None:
    target_string = target_string.casefold().replace(" ", "").replace("-", "")
    for member in enum_class:
        if str(member.value).casefold().replace(" ", "").replace("-", "") == target_string or (
            check_keys and member.name.casefold().replace(" ", "").replace("-", "") == target_string
        ):
            return member
    return None
