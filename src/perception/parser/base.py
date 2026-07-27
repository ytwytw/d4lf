import logging
import re

from src.item import (
    Affix,
    AffixType,
    Aspect,
    Dataloader,
    Item,
    ItemRarity,
    ItemType,
    SeasonalAttribute,
    SigilRules,
    is_consumable,
    is_seal_or_charm,
)
from src.perception.framing import ItemIdentifier
from src.perception.text import correct_name, find_number, keep_letters_and_spaces

LOGGER = logging.getLogger(__name__)

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


def _is_affix_stop_marker(line: str) -> bool:
    normalized = line.lower()
    return any(normalized.startswith(marker) for marker in _AFFIX_STOP_MARKERS) or Dataloader().grammar.startswith(
        "affix_stop", line
    )


def _get_affix_counts(tts_section: list[str], item: Item, start: int) -> tuple[int, int]:
    inherent_num = 0
    affixes_num = 4
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

    if item.item_type == ItemType.HoradricSeal and start < len(tts_section):
        inherent_num = int(_is_charm_slot_unlock(tts_section[start]))

    if item.rarity in [ItemRarity.Unique, ItemRarity.Mythic] and item.name is not None:
        unique_data = Dataloader().aspect_unique_dict.get(item.name)
        unique_inherents = unique_data.get("num_inherents") if unique_data is not None else None
        if type(unique_inherents) is int:
            inherent_num = unique_inherents

    next_line_index = start + inherent_num + affixes_num
    if (
        item.rarity in [ItemRarity.Magic, ItemRarity.Rare]
        and next_line_index < len(tts_section)
        and _is_known_affix_text(tts_section[next_line_index], item.item_type)
        and not _is_affix_stop_marker(tts_section[next_line_index])
    ):
        affixes_num = affixes_num + 1
    elif (
        item.rarity == ItemRarity.Legendary
        and start + inherent_num + affixes_num - 1 < len(tts_section)
        and Dataloader().grammar.startswith("imprinted", tts_section[start + inherent_num + affixes_num - 1])
    ):
        # Additionally, if someone imprinted a 3 affix rare we'd think it was a legendary so we need to catch those here
        affixes_num = 3
    elif item.rarity in [ItemRarity.Legendary, ItemRarity.Unique, ItemRarity.Mythic]:
        while (
            next_line_index < len(tts_section)
            and _is_known_affix_text(tts_section[next_line_index], item.item_type)
            and not _is_affix_stop_marker(tts_section[next_line_index])
        ):
            affixes_num += 1
            next_line_index += 1

    if item.seasonal_attribute == SeasonalAttribute.bloodied:
        affixes_num = affixes_num + 1

    return inherent_num, affixes_num


def _compute_affix_layout(tts_section: list[str], item: Item) -> tuple[int, int, list[str], str | None]:
    """Return inherent count, affix count, affix lines, and following aspect or set text."""
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


def _is_charm_slot_unlock(text: str) -> bool:
    normalized = text.lower()
    grammar = Dataloader().grammar
    return grammar.contains("charm_slot", text) and (normalized.startswith("unlocks ") or grammar.locale != "enUS")


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
    if len(tts_item) < 2:
        return None
    item = Item(original_name=tts_item[0])
    catalog = Dataloader()
    grammar = catalog.grammar
    if grammar.identifier_matches(ItemIdentifier.COMPASS.name, tts_item[1], mode="endswith"):
        return _update_item_object(item, rarity=ItemRarity.Common, item_type=ItemType.Compass)
    if grammar.identifier_matches(ItemIdentifier.NIGHTMARE_SIGIL.name, tts_item[0]):
        if "Nightmare Sigil is used" in tts_item[0]:  # This is actually the crafting screen
            return None
        if grammar.contains("bloodied", tts_item[1]):
            item.seasonal_attribute = SeasonalAttribute.bloodied
        return _update_item_object(item, item_type=ItemType.Sigil)
    if grammar.identifier_matches(ItemIdentifier.ESCALATION_SIGIL.name, tts_item[0], mode="startswith"):
        return _update_item_object(item, item_type=ItemType.EscalationSigil)
    if grammar.identifier_matches(ItemIdentifier.TRIBUTE.name, tts_item[1]):
        item.item_type = ItemType.Tribute
        item.rarity = _get_item_rarity(tts_item[1])
        if item.rarity is None:
            return None
        tribute_text = grammar.strip_rarity(tts_item[1], item.rarity.name)
        item.name = (
            catalog.resolve_tribute(tts_item[0]) or catalog.resolve_tribute(tribute_text) or correct_name(tribute_text)
        )
        return item
    if grammar.identifier_matches(ItemIdentifier.WHISPERING_KEY.name, tts_item[0], mode="startswith"):
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
        catalog.resolve_unique(tts_item[0]) or raw_name
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


from src.perception.parser.details import (  # ruff:ignore[module-import-not-at-top-of-file]
    _get_affix_from_text,
    _get_affix_starting_location_from_tts_section,
    _get_affixes_from_tts_section,
    _get_aspect_from_name,
    _get_aspect_from_text,
    _get_aspect_or_set_from_tts_section,
    _get_item_rarity,
    _get_item_type,
    _is_known_affix_text,
    _update_item_object,
)
