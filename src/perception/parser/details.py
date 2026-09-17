import logging
import re
from typing import TYPE_CHECKING

from src.game_data import GameCatalog, ItemRarity, ItemType, is_armor, is_jewelry, is_weapon
from src.item import Affix, AffixType, Aspect
from src.perception.text import correct_name

if TYPE_CHECKING:
    from src.item import Item

from src.perception.parser.base import _AFFIX_RE, _AFFIX_REPLACEMENTS, _ASPECT_RE, _REPLACE_COMPARE_RE
from src.perception.text import keep_letters_and_spaces

LOGGER = logging.getLogger(__name__)
_DURATION_RES = (
    re.compile(r"for (?P<durationvalue>\d+(?:\.\d+)?) seconds?", re.IGNORECASE),
    re.compile(r"持续\s*(?P<durationvalue>\d+(?:\.\d+)?)\s*秒"),
)


def _update_item_object(item: Item, rarity: ItemRarity | None = None, item_type: ItemType | None = None) -> Item:
    if rarity:
        item.rarity = rarity
    if item_type:
        item.item_type = item_type

    return item


def _get_affix_starting_location_from_tts_section(tts_section: list[str], item: Item) -> int:
    start = 0

    if is_weapon(item.item_type):
        start = _get_index_of_armor_dps_or_all_resist(tts_section, "damage_per_second") + 2
    elif is_jewelry(item.item_type):
        start = _get_index_of_armor_dps_or_all_resist(tts_section, "all_resist")
    elif item.item_type == ItemType.Shield:
        start = _get_index_of_armor_dps_or_all_resist(tts_section, "armor") + 2
    elif is_armor(item.item_type):
        start = _get_index_of_armor_dps_or_all_resist(tts_section, "armor")
    elif item.item_type == ItemType.HoradricSeal:
        index = _get_index_after_item_power(tts_section, fallback=4)
        return _skip_armory_loadout_banner(tts_section, index)
    elif item.item_type == ItemType.Charm:
        index = _get_index_after_item_power(tts_section, fallback=3)
        return _skip_armory_loadout_banner(tts_section, index)
    start += 1

    return start


def _skip_armory_loadout_banner(tts_section: list[str], index: int) -> int:
    """Equipped seals/charms may show an "Armory Loadout" banner right after Item Power; skip past it."""
    if index < len(tts_section) and GameCatalog().grammar.contains("armory_loadout", tts_section[index]):
        return index + 1
    return index


def _get_index_of_armor_dps_or_all_resist(tts_section: list[str], indicator: str) -> int:
    for i, line in enumerate(tts_section):
        clean_line = keep_letters_and_spaces(_REPLACE_COMPARE_RE.sub("", line.lower())).strip()
        if GameCatalog().grammar.equals(indicator, clean_line):
            return i

    return 0


def _get_index_after_item_power(tts_section: list[str], fallback: int) -> int:
    """Get index after item power.

    Seals/charms have no unique anchor text near their affixes (unlike "armor"/"all resist"/"damage per
    second" for other item types), so we anchor on the "Item Power" line instead. This stays correct even
    when Diablo inserts extra lines above it, e.g. an Armory loadout banner on equipped charms/seals.
    """
    for i, line in enumerate(tts_section):
        if GameCatalog().grammar.contains("item_power", line):
            return i + 1

    LOGGER.warning(f"Could not find 'Item Power' line in TTS section, falling back to index {fallback}: {tts_section}")
    return fallback


def _get_affixes_from_tts_section(tts_section: list[str], start: int, length: int) -> list[str]:
    return tts_section[start : start + length]


def _get_aspect_or_set_from_tts_section(tts_section: list[str], item: Item, start: int, num_affixes: int) -> str | None:
    if item.item_type == ItemType.HoradricSeal and item.rarity == ItemRarity.Legendary:
        return None
    # Grab the aspect/set as well in this case
    if item.rarity in [ItemRarity.Mythic, ItemRarity.Unique, ItemRarity.Legendary]:
        aspect_index = start + num_affixes
        return tts_section[aspect_index] if aspect_index < len(tts_section) else None
    if item.rarity == ItemRarity.Set:
        for line in tts_section[start + num_affixes :]:
            set_name = _get_set_from_text(line)
            if set_name:
                return set_name

    return None


def _get_set_from_text(set_text: str) -> str | None:
    set_name = correct_name(set_text)
    if set_name in GameCatalog().bad_tts_uniques:
        set_name = GameCatalog().bad_tts_uniques[set_name]
    if set_name in GameCatalog().set_list:
        return set_name
    return None


def _affix_range_precision(text: str) -> str | None:
    precisions: set[str] = set()
    for match in _AFFIX_RE.finditer(_clean_value_text(text)):
        groups = match.groupdict()
        for suffix in ("1", "2"):
            minimum = groups.get(f"minvalue{suffix}")
            maximum = groups.get(f"maxvalue{suffix}")
            if minimum is None or maximum is None:
                continue
            precisions.add("decimal" if "." in minimum and "." in maximum else "integer")
    return next(iter(precisions)) if len(precisions) == 1 else None


def _resolve_affix_name(text: str, item_type: ItemType | None = None, *, exact: bool = False) -> str | None:
    display_text = keep_letters_and_spaces(_REPLACE_COMPARE_RE.sub("", text).strip())
    display_text = re.sub(r"^[xX]\s+", "", display_text)
    catalog = GameCatalog()
    resolver = catalog.resolve_affix_exact if exact else catalog.resolve_affix
    return resolver(
        display_text,
        include_charms=item_type == ItemType.Charm,
        include_seals=item_type == ItemType.HoradricSeal,
        range_precision=_affix_range_precision(text),
    )


def _get_affix_from_text(text: str, item_type: ItemType | None = None) -> Affix:
    result = Affix(text=text)

    text = _clean_value_text(text)

    for duration_re in _DURATION_RES:
        for duration_match in tuple(duration_re.finditer(text)):
            duration_value = duration_match.group("durationvalue")
            text = text.replace(duration_match.group(0), "")
            text = text.replace(f"[{duration_value}]", "")

    matched_groups: dict[str, str] = {}
    for match in _AFFIX_RE.finditer(text):
        matched_groups = {name: value for name, value in match.groupdict().items() if isinstance(value, str)}
    if not matched_groups and _has_numbers(text):
        msg = f"Could not match affix text: {text}"
        raise Exception(msg)
    for x in ["minvalue1", "minvalue2"]:
        if (value := matched_groups.get(x)) is not None:
            result.min_value = float(value)
            break
    for x in ["maxvalue1", "maxvalue2"]:
        if (value := matched_groups.get(x)) is not None:
            result.max_value = float(value)
            break
    for x in ["affixvalue1", "affixvalue2", "affixvalue3", "affixvalue4"]:
        if (value := matched_groups.get(x)) is not None:
            result.value = float(value)
            break
    for x in ["greateraffix1", "greateraffix2"]:
        if matched_groups.get(x) is not None:
            result.type = AffixType.greater
            if x == "greateraffix2":
                result.value = float(matched_groups[x])
            break
    if (only_value := matched_groups.get("onlyvalue")) is not None:
        result.min_value = float(only_value)
        result.max_value = float(only_value)

    if GameCatalog().grammar.contains("charm_slot", text):
        result.type = AffixType.normal

    resolved_name = _resolve_affix_name(result.text, item_type)
    if resolved_name is None:
        msg = f"Could not resolve affix name: {result.text}"
        raise ValueError(msg)
    result.name = resolved_name
    return result


def _has_numbers(affix_text: str) -> bool:
    return any(char.isdigit() for char in affix_text)


def _clean_value_text(text: str) -> str:
    """Strip the noise tokens (%, +, commas, comparison parentheses, etc.) that surround a numeric value."""
    for x in _AFFIX_REPLACEMENTS:
        text = text.replace(x, "")
    return _REPLACE_COMPARE_RE.sub("", text).strip()


def _get_affix_dictionary(item_type: ItemType | None) -> dict[str, str]:
    if item_type == ItemType.HoradricSeal:
        return GameCatalog().affix_dict | GameCatalog().seal_affix_dict
    if item_type == ItemType.Charm:
        return GameCatalog().affix_dict | GameCatalog().charm_affix_dict
    return GameCatalog().affix_dict


def _is_known_affix_text(text: str, item_type: ItemType | None) -> bool:
    return _resolve_affix_name(text, item_type, exact=True) is not None


# For unique aspects
def _get_aspect_from_text(text: str, name: str) -> Aspect:
    result = Aspect(text=text, name=name)
    text = _clean_value_text(text)

    match = _ASPECT_RE.search(text)
    if match:  # No match means the aspect is text only, there are no values to filter on
        matched_groups = {name: value for name, value in match.groupdict().items() if value is not None}
        if not matched_groups:
            msg = f"Could not match aspect text: {text}"
            raise Exception(msg)

        if matched_groups.get("minvalue") is not None:
            result.min_value = float(matched_groups["minvalue"])
        if matched_groups.get("maxvalue") is not None:
            result.max_value = float(matched_groups["maxvalue"])
        if matched_groups.get("affixvalue") is not None:
            result.value = float(matched_groups["affixvalue"])

    return result


# For legendary aspects
def _get_aspect_from_name(text: str, name: str) -> Aspect | None:
    for aspect_name in GameCatalog().aspect_list:
        if aspect_name in name:
            return Aspect(text=text, name=aspect_name)

    LOGGER.warning(f"Could not find an aspect representing {name} in our data.")
    return None


def _get_item_rarity(data: str) -> ItemRarity | None:
    catalog = GameCatalog()
    normalized = catalog.grammar.strip_terms(data, "ancestral", "bloodied")
    rarity_name = catalog.grammar.rarity_name(normalized)
    if isinstance(rarity_name, str) and rarity_name in ItemRarity.__members__:
        return ItemRarity[rarity_name]
    return ItemRarity.Common if catalog.resolve_item_type(normalized) else None


def _get_item_type(data: str) -> ItemType | None:
    return GameCatalog().item_type_from_text(data)


def _item_type_text_matches(data: str, item_type: ItemType) -> bool:
    normalized = data.strip().casefold()
    return any(normalized == candidate.strip().casefold() for candidate in GameCatalog().item_type_names(item_type))


def _has_item_type_suffix(data: str, item_type: ItemType) -> bool:
    normalized = data.strip().casefold()
    return any(
        normalized.endswith(candidate.strip().casefold()) for candidate in GameCatalog().item_type_names(item_type)
    )


def _has_item_type_prefix(data: str, item_type: ItemType) -> bool:
    normalized = data.strip().casefold()
    return any(
        normalized.startswith(candidate.strip().casefold()) for candidate in GameCatalog().item_type_names(item_type)
    )


def _is_codex_upgrade(tts_section: list[str]) -> bool:
    return any(
        "upgrades an aspect in the codex of power" in line.lower() or "unlocks new aspect" in line.lower()
        for line in tts_section
    )


def _is_cosmetic_upgrade(tts_section: list[str]) -> bool:
    return any("unlocks new look on salvage" in line.lower() for line in tts_section)
