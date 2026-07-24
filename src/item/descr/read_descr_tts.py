import copy
import logging
import re
from typing import TYPE_CHECKING

import src.tts
from src import TP
from src.dataloader import Dataloader
from src.item.data.affix import Affix, AffixType
from src.item.data.aspect import Aspect
from src.item.data.item_type import (
    ItemType,
    is_armor,
    is_consumable,
    is_jewelry,
    is_non_sigil_mapping,
    is_seal_or_charm,
    is_sigil,
    is_socketable,
    is_weapon,
)
from src.item.data.rarity import ItemRarity
from src.item.data.seasonal_attribute import SeasonalAttribute
from src.item.descr import keep_letters_and_spaces
from src.item.descr.text import find_number
from src.item.descr.texture import find_affix_bullets, find_aspect_bullet, find_seperator_short, find_seperators_long
from src.item.models import Item
from src.item.sigil_rules import SigilRules
from src.scripts import correct_name
from src.tts_framing import ItemIdentifiers

if TYPE_CHECKING:
    import numpy as np

    from src.template_finder import TemplateMatch

_AFFIX_RE = re.compile(
    r"(?P<affixvalue1>[0-9]+)[^0-9]+\[(?P<minvalue1>[0-9]+) - (?P<maxvalue1>[0-9]+)]|"
    r"(?P<affixvalue2>[0-9]+\.[0-9]+).+?\[(?P<minvalue2>[0-9]+\.[0-9]+) - (?P<maxvalue2>[0-9]+\.[0-9]+)]|"
    r"(?P<affixvalue3>[.0-9]+)[^0-9]+\[(?P<onlyvalue>[.0-9]+)]|"
    r".?![^\[\]]*[\[\]](?P<affixvalue4>\d+.?:\.\d+?)(?P<greateraffix1>[ ]*)|"
    r"(?P<greateraffix2>[0-9]+[.0-9]*)(?![^\[]*\[).*",
    re.DOTALL,
)

_ASPECT_RE = re.compile(
    r"(?P<affixvalue>[0-9]+[.]?[0-9]*)[^0-9]+\[(?P<minvalue>[0-9]+[.]?[0-9]*)"
    r" - (?P<maxvalue>[0-9]+[.]?[0-9]*)]"
)

_DURATION_RES = (
    re.compile(r"for (?P<durationvalue>\d+(?:\.\d+)?) seconds?", re.IGNORECASE),
    re.compile(r"\u6301\u7eed\s*(?P<durationvalue>\d+(?:\.\d+)?)\s*\u79d2"),
)

_REPLACE_COMPARE_RE = re.compile(r"[\(（].*?[\)）]")

_AFFIX_REPLACEMENTS = ["%", "+", ",", "[+]", "[x]", "per 5 Seconds"]
_AFFIX_STOP_MARKERS = (
    "empty socket",
    "requires level",
    "properties lost when equipped",
    "cannot salvage",
    "sell value",
    "rampage:",
    "feast:",
    "hunger:",
    "right mouse button",
    "left mouse button",
    "action button",
)
_SEASONAL_AFFIX_MARKERS = ("rampage:", "feast:", "hunger:")
LOGGER = logging.getLogger(__name__)


def _is_affix_stop_marker(line: str) -> bool:
    normalized = line.lower()
    return any(normalized.startswith(marker) for marker in _AFFIX_STOP_MARKERS) or Dataloader().grammar.startswith(
        "affix_stop", line
    )


def _resolve_affix_name(text: str, item_type: ItemType | None = None, *, exact: bool = False) -> str | None:
    display_text = keep_letters_and_spaces(_REPLACE_COMPARE_RE.sub("", text).strip())
    catalog = Dataloader()
    resolver = catalog.resolve_affix_exact if exact else catalog.resolve_affix
    return resolver(
        display_text,
        include_charms=item_type == ItemType.Charm,
        include_seals=item_type == ItemType.HoradricSeal,
        range_precision=_affix_range_precision(text),
    )


def _affix_range_precision(text: str) -> str | None:
    """Preserve tooltip range formatting when localized labels alone are ambiguous."""
    precisions: set[str] = set()
    for match in _AFFIX_RE.finditer(_clean_value_text(text)):
        groups = match.groupdict()
        for suffix in ("1", "2"):
            minimum = groups.get(f"minvalue{suffix}")
            maximum = groups.get(f"maxvalue{suffix}")
            if minimum is None or maximum is None:
                continue
            if "." in minimum and "." in maximum:
                precisions.add("decimal")
            elif "." not in minimum and "." not in maximum:
                precisions.add("integer")
    return next(iter(precisions)) if len(precisions) == 1 else None


def _legendary_affix_count(tts_section: list[str], start: int, inherent_num: int) -> int | None:
    """Use the aspect boundary so current-season four- and five-affix items both parse correctly."""
    grammar = Dataloader().grammar
    for index in range(start, len(tts_section)):
        if grammar.startswith("imprinted", tts_section[index]):
            return index - start - inherent_num

    for index in range(start, len(tts_section)):
        if not _is_affix_stop_marker(tts_section[index]):
            continue
        if tts_section[index].lower().startswith(_SEASONAL_AFFIX_MARKERS):
            continue
        affixes_num = index - start - inherent_num - 1
        return affixes_num if affixes_num >= 0 else None
    return None


def _resolved_affix_count(
    tts_section: list[str], item: Item, start: int, inherent_num: int, default_affix_num: int
) -> int | None:
    """Count consecutive known affixes without consuming aspect or filled-socket lines."""
    resolved_count = 0
    for line in tts_section[start:]:
        is_seasonal_affix = item.seasonal_attribute == SeasonalAttribute.bloodied and line.lower().startswith(
            _SEASONAL_AFFIX_MARKERS
        )
        if _is_affix_stop_marker(line) and not is_seasonal_affix:
            break
        if not _resolve_affix_name(line, item.item_type, exact=True):
            break
        resolved_count += 1

    minimum_count = inherent_num + default_affix_num
    if resolved_count >= minimum_count:
        return resolved_count - inherent_num
    return None


# Returns a tuple with the number of affixes.  It's in the format (inherent_num, affixes_num)
def _get_affix_counts(tts_section: list[str], item: Item, start: int) -> tuple[int, int]:
    inherent_num = 0
    affixes_num = 4
    # We assume these objects have the minimum number of affixes and then try to determine if they have more.
    if item.rarity == ItemRarity.Common:
        affixes_num = 0
    elif item.rarity == ItemRarity.Magic:
        affixes_num = 1
    elif item.rarity == ItemRarity.Rare:
        affixes_num = 2 if is_seal_or_charm(item.item_type) else 3
    elif item.rarity == ItemRarity.Legendary:
        affixes_num = 3 if is_seal_or_charm(item.item_type) else 4
    elif item.rarity == ItemRarity.Set:
        affixes_num = 2
    elif item.rarity == ItemRarity.Unique:
        affixes_num = 2 if is_seal_or_charm(item.item_type) else 4

    if item.rarity in [ItemRarity.Unique, ItemRarity.Mythic] and item.name is not None:
        # Uniques can have variable amounts of inherents.
        unique_inherents = (Dataloader().aspect_unique_dict.get(item.name) or {}).get("num_inherents")
        if unique_inherents is not None:
            inherent_num = unique_inherents

        dynamic_unique_count = _resolved_affix_count(tts_section, item, start, inherent_num, affixes_num)
        if dynamic_unique_count is not None:
            affixes_num = dynamic_unique_count

    dynamic_count = None
    if item.rarity == ItemRarity.Legendary and not is_seal_or_charm(item.item_type):
        dynamic_count = _resolved_affix_count(tts_section, item, start, inherent_num, affixes_num)
        if dynamic_count is None:
            dynamic_count = _legendary_affix_count(tts_section, start, inherent_num)
        if dynamic_count is not None:
            affixes_num = dynamic_count

    # Rares have either 3 or 4 affixes so we have to do special handling to figure out where exactly the affixes end.
    # This will also grab up slotted gems but we really don't have much choice
    next_line_index = start + inherent_num + affixes_num
    if (
        item.rarity in [ItemRarity.Magic, ItemRarity.Rare]
        and next_line_index < len(tts_section)
        and not _is_affix_stop_marker(tts_section[next_line_index])
    ):
        affixes_num = affixes_num + 1
    elif item.rarity == ItemRarity.Legendary and Dataloader().grammar.startswith(
        "imprinted", tts_section[start + inherent_num + affixes_num - 1]
    ):
        # Additionally, if someone imprinted a 3 affix rare we'd think it was a legendary so we need to catch those here
        affixes_num = 3

    if item.seasonal_attribute == SeasonalAttribute.bloodied and dynamic_count is None:
        affixes_num = affixes_num + 1

    return inherent_num, affixes_num


def _compute_affix_layout(tts_section: list[str], item: Item) -> tuple[int, int, list[str], str | None]:
    """Compute where affixes start/end and what (if any) aspect/set text follows them.

    Returns (inherent_num, affixes_num, affixes, aspect_or_set_text).
    """
    starting_index = _get_affix_starting_location_from_tts_section(tts_section, item)
    inherent_num, affixes_num = _get_affix_counts(tts_section, item, starting_index)
    affixes = _get_affixes_from_tts_section(tts_section, starting_index, inherent_num + affixes_num)
    aspect_or_set_text = _get_aspect_or_set_from_tts_section(tts_section, item, starting_index, len(affixes))
    return inherent_num, affixes_num, affixes, aspect_or_set_text


def _assign_aspect_or_set(item: Item, aspect_or_set_text: str | None) -> None:
    if not aspect_or_set_text or item.name is None:
        return
    if item.rarity == ItemRarity.Mythic:
        item.aspect = Aspect(name=item.name, text=aspect_or_set_text, value=find_number(aspect_or_set_text))
    elif item.rarity == ItemRarity.Unique:
        item.aspect = _get_aspect_from_text(aspect_or_set_text, item.name)
    elif item.rarity == ItemRarity.Set:
        item.set = aspect_or_set_text
    else:
        item.aspect = _get_aspect_from_name(aspect_or_set_text, item.name)


def _add_affixes_from_tts(tts_section: list[str], item: Item) -> Item:
    inherent_num, affixes_num, affixes, aspect_or_set_text = _compute_affix_layout(tts_section, item)
    for i, affix_text in enumerate(affixes):
        if i < inherent_num:
            affix = _get_affix_from_text(affix_text, item.item_type)
            affix.type = AffixType.inherent
            item.inherent.append(affix)
        elif i < inherent_num + affixes_num:
            affix = _get_affix_from_text(affix_text, item.item_type)
            item.affixes.append(affix)

    _assign_aspect_or_set(item, aspect_or_set_text)
    return item


def _add_affixes_from_tts_mixed(
    tts_section: list[str],
    item: Item,
    affix_bullets: list[TemplateMatch],
    img_item_descr: np.ndarray,
    aspect_bullet: TemplateMatch | None,
) -> Item:
    inherent_num, affixes_num, affixes, aspect_or_set_text = _compute_affix_layout(tts_section, item)

    # A seal will always have one extra bullet that represents the number of slots
    if item.item_type == ItemType.HoradricSeal:
        affix_bullets.pop(0)

    # With advanced item compare on we'll actually find more bullets than we need, so we don't rely on them for
    # number of affixes
    if len(affixes) > len(affix_bullets):
        _raise_index_error(affixes, affix_bullets, item, img_item_descr)

    for i, affix_text in enumerate(affixes):
        if i < inherent_num:
            affix = _get_affix_from_text(affix_text, item.item_type)
            affix.type = AffixType.inherent
            affix.loc = affix_bullets[i].center
            item.inherent.append(affix)
        elif i < inherent_num + affixes_num:
            affix = _get_affix_from_text(affix_text, item.item_type)
            affix.loc = affix_bullets[i].center
            if affix_bullets[i].name.startswith("greater_affix"):
                affix.type = AffixType.greater
            elif affix_bullets[i].name.startswith("rerolled"):
                affix.type = AffixType.rerolled
            elif affix_bullets[i].name.startswith("tempered_affix"):
                affix.type = AffixType.tempered
            elif affix.type != AffixType.greater:
                affix.type = AffixType.normal
            item.affixes.append(affix)

    _assign_aspect_or_set(item, aspect_or_set_text)
    if item.aspect and aspect_bullet:
        item.aspect.loc = aspect_bullet.center
    return item


def _raise_index_error(affixes, affix_bullets, item, img_item_descr: np.ndarray):
    LOGGER.error("About to raise index error, dumping information for debug:")
    LOGGER.error(f"Affixes ({len(affixes)}): {affixes}")
    LOGGER.error(f"Affix Bullets ({len(affix_bullets)}): {affix_bullets}")
    LOGGER.error(f"Item: {item}")

    msg = (
        "Found more affixes than we found bullets to represent those affixes. "
        "This could be a temporary issue finding bullet positions on the screen, "
        "but if it happens consistently please open a bug report with a full screen "
        "screenshot with the item hovered on and vision mode disabled. Additionally, "
        "include the ~10 log lines above this message and the screenshot in the screenshot folder."
    )
    raise IndexError(msg)


def _add_sigil_affixes_from_tts(tts_section: list[str], item: Item) -> Item:
    catalog = Dataloader()
    name_index = (
        3 if item.item_type == ItemType.EscalationSigil or item.seasonal_attribute == SeasonalAttribute.bloodied else 2
    )
    raw_name = tts_section[name_index]
    item.name = catalog.resolve_sigil(raw_name, "dungeons") or correct_name(raw_name.split(" in ")[0]) or ""

    start = next((i for i, line in enumerate(tts_section) if catalog.grammar.contains("affixes_header", line)), None)
    if start is not None:
        first_affix_index = start + 1
        second_affix_index = start + 3
    else:
        msg = f"Could not find string AFFIXES in TTS provided by Diablo. Sigil filtering may be unstable, please open a bug with this info: {tts_section}"
        LOGGER.error(msg)
        first_affix_index = 4
        second_affix_index = 6

    affixes = [tts_section[first_affix_index], tts_section[second_affix_index]]

    for affix_name in affixes:
        cleaned_name = keep_letters_and_spaces(affix_name)
        canonical_name = catalog.resolve_sigil(cleaned_name, "major", "minor", "positive")
        affix = Affix(name=canonical_name or correct_name(cleaned_name) or "")
        affix.type = AffixType.normal
        item.affixes.append(affix)

    item.rarity = SigilRules.default().for_item(item).rarity

    return item


def _create_base_item_from_tts(tts_item: list[str]) -> Item | None:
    item = Item(original_name=tts_item[0])
    grammar = Dataloader().grammar
    if grammar.identifier_matches(ItemIdentifiers.COMPASS.name, tts_item[1], mode="endswith"):
        return _update_item_object(item, rarity=ItemRarity.Common, item_type=ItemType.Compass)
    if grammar.identifier_matches(ItemIdentifiers.NIGHTMARE_SIGIL.name, tts_item[0]):
        if "Nightmare Sigil is used" in tts_item[0]:  # This is actually the crafting screen
            return None
        if grammar.contains("bloodied", tts_item[1]):
            item.seasonal_attribute = SeasonalAttribute.bloodied
        return _update_item_object(item, item_type=ItemType.Sigil)
    if grammar.identifier_matches(ItemIdentifiers.ESCALATION_SIGIL.name, tts_item[0], mode="startswith"):
        return _update_item_object(item, item_type=ItemType.EscalationSigil)
    if grammar.identifier_matches(ItemIdentifiers.TRIBUTE.name, tts_item[0]):
        item.item_type = ItemType.Tribute
        item.rarity = _get_item_rarity(tts_item[1])
        if item.rarity is None:
            return None
        tribute_text = grammar.strip_rarity(tts_item[1], item.rarity.name)
        item.name = Dataloader().resolve_tribute(tribute_text) or correct_name(tribute_text)
        return item
    if grammar.identifier_matches(ItemIdentifiers.WHISPERING_KEY.name, tts_item[0], mode="startswith"):
        return _update_item_object(item, item_type=ItemType.Consumable)
    if any(tts_item[1].lower().endswith(x) for x in ["summoning"]):
        return _update_item_object(item, item_type=ItemType.Material)
    if any(tts_item[1].lower().endswith(x) for x in ["gem"]):
        return _update_item_object(item, item_type=ItemType.Gem)
    if any(tts_item[1].lower().endswith(x) for x in ["whispering wood"]):
        return _update_item_object(item, item_type=ItemType.WhisperingWood)
    if any(tts_item[1].lower().startswith(x) for x in ["cosmetic"]):
        return _update_item_object(item, item_type=ItemType.Cosmetic)
    if any(tts_item[1].lower().endswith(x) for x in ["boss key"]):
        return _update_item_object(item, item_type=ItemType.LairBossKey)
    if "rune of" in tts_item[1].lower():
        item.item_type = ItemType.Rune
        search_string_split = tts_item[1].lower().split(" rune of ")
        item.rarity = _get_item_rarity(search_string_split[0])
        return item
    if any(grammar.contains("cost", value) for value in tts_item):
        item.is_in_shop = True
    if any(tts_item[1].lower().endswith(x) for x in ["cache"]):
        item.item_type = ItemType.Cache
        return item
    if tts_item[1].lower().endswith("elixir"):
        item.item_type = ItemType.Elixir
    elif tts_item[1].lower().endswith("incense"):
        item.item_type = ItemType.Incense
    elif "temper manual" in tts_item[1].lower():
        item.item_type = ItemType.TemperManual
    elif any(tts_item[1].lower().endswith(x) for x in ["consumable", "scroll"]):
        item.item_type = ItemType.Consumable
    if is_consumable(item.item_type):
        search_string_split = tts_item[1].split(" ")
        item.rarity = _get_item_rarity(search_string_split[0])
        if item.rarity is None:
            return None
        return item
    if grammar.contains("bloodied", tts_item[1]):
        item.seasonal_attribute = SeasonalAttribute.bloodied
    item.is_ancestral = grammar.contains("ancestral", tts_item[1])

    # Check lines 3-6 instead of just line 4 (handles variable name lengths and gives us flexibility to search for the sanctified marker)
    if any(grammar.contains("sanctified", tts_item[i]) for i in range(3, min(7, len(tts_item)))):
        item.seasonal_attribute = SeasonalAttribute.sanctified

    search_string = grammar.strip_terms(tts_item[1], "ancestral", "bloodied")
    search_string = _REPLACE_COMPARE_RE.sub("", search_string).strip()
    item.rarity = _get_item_rarity(search_string)
    if item.rarity is None:
        return None
    item.item_type = _get_item_type(grammar.strip_rarity(search_string, item.rarity.name))
    if item.item_type is None:
        return None
    raw_name = correct_name(tts_item[0]) or ""
    item.name = (
        Dataloader().resolve_unique(tts_item[0]) or raw_name
        if item.rarity in [ItemRarity.Unique, ItemRarity.Mythic]
        else raw_name
    )
    if item.name in Dataloader().bad_tts_uniques:
        item.name = Dataloader().bad_tts_uniques[item.name]
    for line in tts_item:
        if grammar.contains("item_power", line):
            item_power = find_number(line)
            if item_power is None:
                return None
            item.power = int(item_power)
            break
    return item


def _update_item_object(item: Item, rarity=None, item_type=None) -> Item:
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
        index = _skip_armory_loadout_banner(tts_section, index)
        # Seals also report their max charm slot count right after Item Power; skip past it to reach the affixes.
        if index < len(tts_section) and Dataloader().grammar.contains("charm_slot", tts_section[index]):
            index += 1
        return index
    elif item.item_type == ItemType.Charm:
        index = _get_index_after_item_power(tts_section, fallback=3)
        return _skip_armory_loadout_banner(tts_section, index)
    start += 1

    return start


def _skip_armory_loadout_banner(tts_section: list[str], index: int) -> int:
    """Equipped seals/charms may show an "Armory Loadout" banner right after Item Power; skip past it."""
    if index < len(tts_section) and Dataloader().grammar.contains("armory_loadout", tts_section[index]):
        return index + 1
    return index


def _get_index_of_armor_dps_or_all_resist(tts_section: list[str], indicator: str) -> int:
    for i, line in enumerate(tts_section):
        clean_line = keep_letters_and_spaces(_REPLACE_COMPARE_RE.sub("", line.lower())).strip()
        if Dataloader().grammar.equals(indicator, clean_line):
            return i

    return 0


def _get_index_after_item_power(tts_section: list[str], fallback: int) -> int:
    """Get index after item power.

    Seals/charms have no unique anchor text near their affixes (unlike "armor"/"all resist"/"damage per
    second" for other item types), so we anchor on the "Item Power" line instead. This stays correct even
    when Diablo inserts extra lines above it, e.g. an Armory loadout banner on equipped charms/seals.
    """
    for i, line in enumerate(tts_section):
        if Dataloader().grammar.contains("item_power", line):
            return i + 1

    LOGGER.warning(f"Could not find 'Item Power' line in TTS section, falling back to index {fallback}: {tts_section}")
    return fallback


def _get_affixes_from_tts_section(tts_section: list[str], start: int, length: int):
    return tts_section[start : start + length]


def _get_aspect_or_set_from_tts_section(tts_section: list[str], item: Item, start: int, num_affixes: int):
    if item.item_type == ItemType.HoradricSeal and item.rarity == ItemRarity.Legendary:
        return None
    # Grab the aspect/set as well in this case
    if item.rarity in [ItemRarity.Mythic, ItemRarity.Unique, ItemRarity.Legendary]:
        aspect_index = start + num_affixes
        return tts_section[aspect_index]
    if item.rarity == ItemRarity.Set:
        for line in tts_section[start + num_affixes :]:
            set_name = _get_set_from_text(line)
            if set_name:
                return set_name

    return None


def _get_set_from_text(set_text: str) -> str | None:
    set_name = Dataloader().resolve_set(set_text) or correct_name(set_text) or ""
    if set_name in Dataloader().bad_tts_uniques:
        set_name = Dataloader().bad_tts_uniques[set_name]
    if set_name in Dataloader().set_dict:
        return set_name
    return None


def _get_affix_from_text(text: str, item_type: ItemType | None = None) -> Affix:
    result = Affix(text=text)

    text = _clean_value_text(text)

    # Duration values trail the actual stat in both supported locales and otherwise look like a GA.
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

    if "Charm Slot" in text:  # These are never greater even if they look like they are greater
        result.type = AffixType.normal

    resolved_name = _resolve_affix_name(result.text, item_type)
    if resolved_name is None:
        message = f"Could not resolve affix name: {result.text}"
        raise ValueError(message)
    result.name = resolved_name
    return result


def _has_numbers(affix_text):
    return any(char.isdigit() for char in affix_text)


def _clean_value_text(text: str) -> str:
    """Strip the noise tokens (%, +, commas, comparison parentheses, etc.) that surround a numeric value."""
    for x in _AFFIX_REPLACEMENTS:
        text = text.replace(x, "")
    return _REPLACE_COMPARE_RE.sub("", text).strip()


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
    if aspect_name := Dataloader().resolve_aspect(name):
        return Aspect(text=text, name=aspect_name)

    LOGGER.warning(f"Could not find an aspect representing {name} in our data.")
    return None


def _get_item_rarity(data: str) -> ItemRarity | None:
    rarity_name = Dataloader().grammar.rarity_name(data)
    if isinstance(rarity_name, str) and rarity_name in ItemRarity.__members__:
        return ItemRarity[rarity_name]
    return ItemRarity.Common if Dataloader().resolve_item_type(data) else None


def _get_item_type(data: str):
    item_type_name = Dataloader().resolve_item_type(data)
    return (
        ItemType[item_type_name] if isinstance(item_type_name, str) and item_type_name in ItemType.__members__ else None
    )


def _is_codex_upgrade(tts_section: list[str]) -> bool:
    return any(
        "upgrades an aspect in the codex of power" in line.lower() or "unlocks new aspect" in line.lower()
        for line in tts_section
    )


def _is_cosmetic_upgrade(tts_section: list[str]):
    return any("unlocks new look on salvage" in line.lower() for line in tts_section)


class _TtsItemParser:
    def __init__(
        self, tts_section: list[str], *, img_item_descr: np.ndarray | None = None, attach_locations: bool = False
    ):
        self.tts_section = tts_section
        self.img_item_descr = img_item_descr
        self.attach_locations = attach_locations
        self.item: Item | None = None

    def parse(self) -> Item | None:
        if not self.tts_section:
            return None
        if (item := _create_base_item_from_tts(self.tts_section)) is None:
            return None
        self.item = item

        if self.attach_locations and is_sigil(item.item_type):
            return item
        if is_sigil(item.item_type):
            return _add_sigil_affixes_from_tts(self.tts_section, item)
        if item.item_type == ItemType.Cosmetic and not self.attach_locations:
            item.cosmetic_upgrade = True
            return item
        if self._should_return_without_affixes():
            return item
        if not self._is_supported_equipment():
            return None
        if not self.attach_locations and item.rarity == ItemRarity.Mythic and item.is_in_shop:
            return None

        if self.attach_locations:
            return self._parse_with_locations()

        self._validate_unique()
        self._add_upgrade_flags()
        return _add_affixes_from_tts(self.tts_section, item)

    @property
    def _current_item(self) -> Item:
        if self.item is None:
            msg = "TTS parser item has not been initialized"
            raise RuntimeError(msg)
        return self.item

    def _should_return_without_affixes(self) -> bool:
        item = self._current_item
        terminal_item_types = [ItemType.Material, ItemType.Tribute, ItemType.Cache, ItemType.LairBossKey]
        if not self.attach_locations and item.seasonal_attribute == SeasonalAttribute.sanctified:
            return True
        return any([
            is_consumable(item.item_type),
            is_non_sigil_mapping(item.item_type),
            is_socketable(item.item_type),
            item.item_type in terminal_item_types,
        ])

    def _is_supported_equipment(self) -> bool:
        item = self._current_item
        return any([
            is_armor(item.item_type),
            is_jewelry(item.item_type),
            is_weapon(item.item_type),
            is_seal_or_charm(item.item_type),
        ])

    def _parse_with_locations(self) -> Item | None:
        item = self._current_item
        img_item_descr = self.img_item_descr
        if img_item_descr is None:
            LOGGER.warning("Cannot attach item locations without an item description image.")
            return None
        if (sep_short_match := find_seperator_short(img_item_descr)) is None:
            LOGGER.warning("Could not detect item_seperator_short.")
            return None

        TP.submit(find_seperators_long, img_item_descr, sep_short_match)
        aspect_bullet_future = (
            TP.submit(find_aspect_bullet, img_item_descr, sep_short_match)
            if item.rarity in [ItemRarity.Legendary, ItemRarity.Unique, ItemRarity.Mythic]
            else None
        )
        self._validate_unique()
        self._add_upgrade_flags()
        aspect_bullet = aspect_bullet_future.result() if aspect_bullet_future else None
        _, _, expected_affixes, _ = _compute_affix_layout(self.tts_section, item)
        affix_bullets = find_affix_bullets(
            img_item_descr, sep_short_match, aspect_bullet=aspect_bullet, expected_count=len(expected_affixes)
        )
        return _add_affixes_from_tts_mixed(
            self.tts_section, item, affix_bullets, img_item_descr, aspect_bullet=aspect_bullet
        )

    def _validate_unique(self) -> None:
        item = self._current_item
        if item.rarity in [ItemRarity.Unique, ItemRarity.Mythic] and item.name not in Dataloader().aspect_unique_dict:
            msg = (
                f"Unrecognized unique {item.name}. This most likely means the name of it reported "
                f"from Diablo 4 is wrong. Please report a bug with this message."
            )
            if not self.attach_locations:
                msg = f"{msg} TTS: {self.tts_section}"
            raise IndexError(msg)

    def _add_upgrade_flags(self) -> None:
        item = self._current_item
        item.codex_upgrade = _is_codex_upgrade(self.tts_section)
        item.cosmetic_upgrade = _is_cosmetic_upgrade(self.tts_section)


def read_descr_mixed(img_item_descr: np.ndarray | None) -> Item | None:
    tts_section = copy.copy(src.tts.LAST_ITEM)
    return _TtsItemParser(tts_section, img_item_descr=img_item_descr, attach_locations=True).parse()


def read_descr() -> Item | None:
    tts_section = copy.copy(src.tts.LAST_ITEM)
    return _TtsItemParser(tts_section).parse()
