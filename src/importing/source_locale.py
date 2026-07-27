"""Build-source dictionaries that are independent from the active game locale."""

import json
from functools import cache

from src.item import ItemType
from src.locale_data import normalize_locale_text
from src.settings import BASE_DIR


def _affix_file_name(item_type: ItemType | None) -> str:
    if item_type == ItemType.HoradricSeal:
        return "seals_affixes.json"
    if item_type == ItemType.Charm:
        return "charms_affixes.json"
    return "affixes.json"


@cache
def _load_string_map(locale: str, file_name: str) -> dict[str, str]:
    path = BASE_DIR / "assets" / "lang" / locale / file_name
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in data.items()
    ):
        msg = f"Invalid source data in {locale}/{file_name}"
        raise ValueError(msg)
    return data


@cache
def source_affix_dict_for_item_type(item_type: ItemType | None, source_locale: str) -> dict[str, str]:
    """Load source-site labels, with English display fallbacks for missing keys."""
    file_name = _affix_file_name(item_type)
    selected = _load_string_map(source_locale, file_name)
    if source_locale == "enUS":
        return dict(selected)
    return {**_load_string_map("enUS", file_name), **selected}


@cache
def _source_affix_aliases(item_type: ItemType | None, source_locale: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()
    for canonical, display in source_affix_dict_for_item_type(item_type, source_locale).items():
        for value in (canonical, canonical.replace("_", " "), display):
            normalized = normalize_locale_text(value)
            if not normalized or normalized in ambiguous:
                continue
            existing = aliases.get(normalized)
            if existing is None:
                aliases[normalized] = canonical
            elif existing != canonical:
                aliases.pop(normalized)
                ambiguous.add(normalized)
    return aliases


def match_source_affix(value: str, item_type: ItemType | None, source_locale: str) -> str | None:
    """Resolve a source label exactly, returning None for unknown or ambiguous text."""
    return _source_affix_aliases(item_type, source_locale).get(normalize_locale_text(value))


@cache
def source_set_names(source_locale: str = "enUS") -> tuple[str, ...]:
    path = BASE_DIR / "assets" / "lang" / source_locale / "sets.json"
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    if isinstance(data, list) and all(isinstance(value, str) for value in data):
        return tuple(data)
    if isinstance(data, dict) and all(isinstance(value, str) for value in data):
        return tuple(str(key) for key in data)
    msg = f"Invalid source data in {source_locale}/sets.json"
    raise ValueError(msg)


__all__ = ["match_source_affix", "source_affix_dict_for_item_type", "source_set_names"]
