import logging

from src.game_data import GameCatalog, ItemRarity, ItemType, SigilRules, is_consumable, is_seal_or_charm
from src.item import Affix, AffixType, Aspect, Item, SeasonalAttribute
from src.perception.framing import ItemIdentifier
from src.perception.parser.details import (
    _get_affix_from_text,
    _get_affix_starting_location_from_tts_section,
    _get_affixes_from_tts_section,
    _get_aspect_from_name,
    _get_aspect_from_text,
    _get_aspect_or_set_from_tts_section,
    _get_item_rarity,
    _get_item_type,
    _has_item_type_prefix,
    _has_item_type_suffix,
    _is_known_affix_text,
    _update_item_object,
)
from src.perception.parser.tokens import _REPLACE_COMPARE_RE, _is_affix_stop_marker
from src.perception.parser.tributes import _resolve_tribute_from_tts
from src.perception.text import correct_name, find_number, keep_letters_and_spaces

LOGGER = logging.getLogger(__name__)


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

    if item.rarity in [ItemRarity.Unique, ItemRarity.Mythic] and item.name and item.item_type != ItemType.Charm:
        # Uniques can have variable amounts of inherents.
        unique_data = GameCatalog().aspect_unique_dict.get(item.name)
        if isinstance(unique_data, dict) and isinstance(inherent_value := unique_data.get("num_inherents"), int):
            inherent_num = inherent_value

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
        and GameCatalog().grammar.startswith("imprinted", tts_section[start + inherent_num + affixes_num - 1])
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
    affixes: list[str] = _get_affixes_from_tts_section(tts_section, starting_index, inherent_num + affixes_num)
    if len(affixes) != inherent_num + affixes_num or any(
        _is_affix_stop_marker(line) and not _is_known_affix_text(line, item.item_type) for line in affixes
    ):
        msg = f"Incomplete affix section for {item.original_name}"
        raise ValueError(msg)
    aspect_or_set_text: str | None = _get_aspect_or_set_from_tts_section(
        tts_section, item, starting_index, len(affixes)
    )
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
    grammar = GameCatalog().grammar
    return grammar.contains("charm_slot", text) and (normalized.startswith("unlocks ") or grammar.locale != "enUS")


def _add_sigil_affixes_from_tts(tts_section: list[str], item: Item) -> Item:
    catalog = GameCatalog()
    name_index = (
        3 if item.item_type == ItemType.EscalationSigil or item.seasonal_attribute == SeasonalAttribute.bloodied else 2
    )
    raw_name = tts_section[name_index]
    item.name = catalog.resolve_sigil(raw_name, "dungeons")
    if item.name is None:
        msg = f"Could not resolve sigil dungeon: {raw_name}"
        raise ValueError(msg)

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
        if canonical_name is None:
            msg = f"Could not resolve sigil affix: {affix_name}"
            raise ValueError(msg)
        affix = Affix(name=canonical_name)
        affix.type = AffixType.normal
        item.affixes.append(affix)

    item.rarity = SigilRules.default().for_item(item).rarity

    return item


def _create_base_item_from_tts(tts_item: list[str]) -> Item | None:
    if len(tts_item) < 2:
        return None
    item = Item(original_name=tts_item[0])
    catalog = GameCatalog()
    grammar = catalog.grammar
    if grammar.identifier_matches(ItemIdentifier.COMPASS.name, tts_item[1], mode="endswith"):
        return _update_item_object(item, rarity=ItemRarity.Common, item_type=ItemType.Compass)
    if grammar.identifier_matches(ItemIdentifier.NIGHTMARE_SIGIL.name, tts_item[0]):
        if grammar.contains("sigil_crafting_screen", tts_item[0]):
            return None
        if grammar.contains("bloodied", tts_item[1]):
            item.seasonal_attribute = SeasonalAttribute.bloodied
        return _update_item_object(item, item_type=ItemType.Sigil)
    if grammar.identifier_matches(ItemIdentifier.ESCALATION_SIGIL.name, tts_item[0], mode="startswith"):
        return _update_item_object(item, item_type=ItemType.EscalationSigil)
    if grammar.identifier_matches(ItemIdentifier.TRIBUTE.name, tts_item[1]) or _has_item_type_suffix(
        tts_item[1], ItemType.Tribute
    ):
        item.item_type = ItemType.Tribute
        item.rarity = _get_item_rarity(tts_item[1])
        if item.rarity is None:
            return None
        tribute_text = grammar.strip_rarity(tts_item[1], item.rarity.name)
        item.name = _resolve_tribute_from_tts(tts_item, tribute_text, catalog)
        if item.name is None:
            msg = f"Could not resolve tribute name: {tts_item[0]}"
            raise ValueError(msg)
        return item
    if grammar.identifier_matches(ItemIdentifier.WHISPERING_KEY.name, tts_item[0], mode="startswith"):
        return _update_item_object(item, item_type=ItemType.Consumable)
    if _has_item_type_suffix(tts_item[1], ItemType.Material) or tts_item[1].lower().endswith("summoning"):
        return _update_item_object(item, item_type=ItemType.Material)
    if _has_item_type_suffix(tts_item[1], ItemType.Gem):
        return _update_item_object(item, item_type=ItemType.Gem)
    if _has_item_type_suffix(tts_item[1], ItemType.WhisperingWood):
        return _update_item_object(item, item_type=ItemType.WhisperingWood)
    if _has_item_type_prefix(tts_item[1], ItemType.Cosmetic) or tts_item[1].lower().startswith("cosmetic"):
        return _update_item_object(item, item_type=ItemType.Cosmetic)
    if _has_item_type_suffix(tts_item[1], ItemType.LairBossKey) or tts_item[1].lower().endswith("boss key"):
        return _update_item_object(item, item_type=ItemType.LairBossKey)
    if "rune of" in tts_item[1].lower():
        item.item_type = ItemType.Rune
        search_string_split = tts_item[1].lower().split(" rune of ")
        item.rarity = _get_item_rarity(search_string_split[0])
        return item
    if any(grammar.contains("cost", value) for value in tts_item):
        item.is_in_shop = True
    if _has_item_type_suffix(tts_item[1], ItemType.Cache):
        item.item_type = ItemType.Cache
        return item
    if _has_item_type_suffix(tts_item[1], ItemType.Elixir):
        item.item_type = ItemType.Elixir
    elif _has_item_type_suffix(tts_item[1], ItemType.Incense):
        item.item_type = ItemType.Incense
    elif _has_item_type_suffix(tts_item[1], ItemType.TemperManual):
        item.item_type = ItemType.TemperManual
    elif _has_item_type_suffix(tts_item[1], ItemType.Consumable) or tts_item[1].lower().endswith("scroll"):
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
        catalog.resolve_unique(tts_item[0], item_type=item.item_type) or raw_name
        if item.rarity in [ItemRarity.Unique, ItemRarity.Mythic]
        else raw_name
    )
    if item.name in catalog.bad_tts_uniques:
        item.name = catalog.bad_tts_uniques[item.name]
    for line in tts_item:
        if grammar.contains("item_power", line):
            item_power = find_number(line)
            if item_power is None:
                return None
            item.power = int(item_power)
            break
    return item
