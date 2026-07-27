"""Convert D2Core equipment records into canonical importer variants."""

import logging
from typing import TYPE_CHECKING, cast

from src.importing.d2core.catalog import CATALOG_LOCALE, D2CoreCatalog
from src.importing.filters import create_item_affix_pool, match_to_enum, update_mingreateraffixcount
from src.importing.pipeline import Variant
from src.importing.source_locale import match_source_affix
from src.item import Affix, AffixType, Dataloader, ItemType
from src.perception import correct_name
from src.profiles import AspectUniqueFilterModel, ItemFilterModel

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from src.importing.contracts import ImportOptions

LOGGER = logging.getLogger(__name__)
UNSUPPORTED_ITEM_TYPES = {ItemType.Charm, ItemType.HoradricSeal}


def extract_d2core_variant(
    gear: Sequence[Mapping[str, object]], catalog: D2CoreCatalog, options: ImportOptions, *, name: str = ""
) -> Variant:
    filters: list[ItemFilterModel] = []
    aspect_upgrades: list[str] = []
    for piece in gear:
        item_type_label = piece.get("itemType")
        item_type = (
            match_to_enum(ItemType, item_type_label, check_keys=True) if isinstance(item_type_label, str) else None
        )
        if item_type is None or item_type in UNSUPPORTED_ITEM_TYPES:
            LOGGER.warning("Skipping D2Core equipment with unsupported item type %r.", item_type_label)
            continue

        unique_like = str(piece.get("type", "")).casefold() in {"unique", "uniqueitem", "mythic"}
        if not unique_like and options.import_aspect_upgrades:
            for aspect_key in (piece.get("key"), piece.get("transfiguredAspect")):
                aspect_name = _resolve_aspect(aspect_key, catalog)
                if aspect_name and aspect_name not in aspect_upgrades:
                    aspect_upgrades.append(aspect_name)

        raw_mods = piece.get("mods")
        affixes = _convert_mods_to_affixes(
            cast("Sequence[object]", raw_mods) if isinstance(raw_mods, list) else [],
            item_type,
            catalog,
            options.import_greater_affixes,
        )
        item_filter = ItemFilterModel(item_type=[item_type], min_power=100)
        if unique_like:
            unique_name = _resolve_unique(piece.get("key"), catalog)
            if not unique_name:
                LOGGER.warning("Skipping unresolved D2Core unique %r.", piece.get("name") or piece.get("key"))
                continue
            item_filter.unique_aspect = [AspectUniqueFilterModel(name=unique_name)]
        if not affixes and not item_filter.unique_aspect:
            LOGGER.warning("Skipping %s because it has no supported affixes.", item_type.name)
            continue
        if affixes:
            item_filter.affix_pool = create_item_affix_pool(affixes=affixes, unique_like=unique_like)
            update_mingreateraffixcount(item_filter, options.require_greater_affixes)
        filters.append(item_filter)
    return Variant(name=name, affix_filters=filters, aspect_upgrade_filters=aspect_upgrades)


def _convert_mods_to_affixes(
    raw_mods: Sequence[object], item_type: ItemType, catalog: D2CoreCatalog, import_greater_affixes: bool
) -> list[Affix]:
    resolved: dict[tuple[str, AffixType], Affix] = {}
    for raw_mod in raw_mods:
        if not isinstance(raw_mod, dict) or not isinstance(source_key := raw_mod.get("name"), str):
            continue
        if source_key.casefold().startswith("tempered_") or raw_mod.get("tempered") is True:
            continue
        aliases = catalog.affix_aliases.get(source_key)
        if aliases is None:
            LOGGER.warning(
                "D2Core affix key %r is not in catalog build %s; skipping it.", source_key, catalog.build_version
            )
            continue
        canonical = next(
            (matched for alias in aliases if (matched := match_source_affix(alias, item_type, CATALOG_LOCALE))), None
        )
        if canonical is None:
            LOGGER.warning("D2Core affix %r has no exact D4LF match; skipping it.", source_key)
            continue
        mapping = cast("Mapping[str, object]", raw_mod)
        affix_type = (
            AffixType.greater
            if import_greater_affixes and _raw_mod_is_greater(mapping, source_key)
            else AffixType.normal
        )
        resolved[canonical, affix_type] = Affix(name=canonical, type=affix_type)
    return sorted(resolved.values(), key=lambda affix: (affix.name, affix.type.value))


def _raw_mod_is_greater(raw_mod: Mapping[str, object], source_key: str) -> bool:
    greater = raw_mod.get("greater")
    explicitly_greater = greater is True or (
        isinstance(greater, int | float) and not isinstance(greater, bool) and greater > 0
    )
    return explicitly_greater or "_greater" in source_key.casefold()


def _resolve_aspect(source_key: object, catalog: D2CoreCatalog) -> str | None:
    if not isinstance(source_key, str) or not source_key:
        return None
    source_name = catalog.aspect_names.get(source_key)
    if source_name is None:
        LOGGER.warning(
            "D2Core aspect key %r is not in catalog build %s; skipping it.", source_key, catalog.build_version
        )
        return None
    canonical = correct_name(source_name.casefold().replace("aspect", "").strip()) or ""
    if canonical in Dataloader().aspect_list:
        return canonical
    LOGGER.warning("D2Core aspect %r has no exact D4LF match; skipping it.", source_name)
    return None


def _resolve_unique(source_key: object, catalog: D2CoreCatalog) -> str | None:
    if not isinstance(source_key, str) or not source_key:
        return None
    source_name = catalog.unique_names.get(source_key)
    if source_name is None:
        return None
    canonical = correct_name(source_name.replace("\u2019", "'")) or ""
    return canonical if canonical in Dataloader().aspect_unique_dict else None
