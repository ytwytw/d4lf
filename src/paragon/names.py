"""Localized Paragon proper names resolved from stable game-data identifiers."""

import json
import re
import unicodedata
from functools import cache
from typing import Literal

from src.settings import BASE_DIR, get_settings

NameKind = Literal["boards", "glyphs"]

_CLASS_PREFIXES = {
    "barb": "barbarian",
    "druid": "druid",
    "necro": "necromancer",
    "paladin": "paladin",
    "rogue": "rogue",
    "sorc": "sorcerer",
    "spirit": "spiritborn",
    "warlock": "warlock",
}
_CLASS_BOARD_PREFIXES = {value: key for key, value in _CLASS_PREFIXES.items()}
_CLASS_ALIASES = {
    "barbarian": "barbarian",
    "druid": "druid",
    "necromancer": "necromancer",
    "paladin": "paladin",
    "rogue": "rogue",
    "sorcerer": "sorcerer",
    "spiritborn": "spiritborn",
    "warlock": "warlock",
}
_START_ALIASES = {"start", "starter board", "starting board", "开始", "初始盘"}


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", " ", text, flags=re.UNICODE).strip()


@cache
def _load_catalog(locale: str) -> dict[NameKind, dict[str, str]]:
    path = BASE_DIR / "assets" / "lang" / locale / "paragon_names.json"
    try:
        with path.open(encoding="utf-8") as source:
            raw = json.load(source)
    except OSError, json.JSONDecodeError:
        return {"boards": {}, "glyphs": {}}

    result: dict[NameKind, dict[str, str]] = {"boards": {}, "glyphs": {}}
    if not isinstance(raw, dict):
        return result
    for kind in result:
        values = raw.get(kind)
        if isinstance(values, dict):
            result[kind] = {
                str(identifier): str(name)
                for identifier, name in values.items()
                if isinstance(identifier, str) and isinstance(name, str)
            }
    return result


@cache
def _name_index(kind: NameKind) -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    for locale in ("enUS", "zhCN"):
        for identifier, name in _load_catalog(locale)[kind].items():
            candidates.setdefault(_normalize(name), set()).add(identifier)
    index = {name: next(iter(identifiers)) for name, identifiers in candidates.items() if len(identifiers) == 1}
    if kind == "glyphs":
        index.setdefault(_normalize("Golems"), _find_identifier(kind, "Golem"))
    return {name: identifier for name, identifier in index.items() if identifier}


def _find_identifier(kind: NameKind, source_name: str) -> str:
    normalized = _normalize(source_name)
    return next(
        (identifier for identifier, name in _load_catalog("enUS")[kind].items() if _normalize(name) == normalized), ""
    )


def paragon_class_slug(identifier: str | None, source_name: str | None = None) -> str:
    """Return a canonical class slug from a board ID or legacy board name."""
    if identifier:
        match = re.match(r"^paragon_([^_]+)_", identifier, flags=re.IGNORECASE)
        if match and (slug := _CLASS_PREFIXES.get(match.group(1).casefold())):
            return slug

    normalized = _normalize(source_name)
    first = normalized.split(" ", 1)[0]
    return _CLASS_ALIASES.get(first, "")


def _starting_board_id(class_slug: str) -> str:
    prefix = _CLASS_BOARD_PREFIXES.get(class_slug)
    if prefix == "spirit":
        return "Paragon_Spirit_0"
    return f"Paragon_{prefix.title()}_00" if prefix else ""


def localized_paragon_name(
    kind: NameKind, *, identifier: str | None, source_name: str | None, class_slug: str = "", locale: str | None = None
) -> str:
    """Resolve a board or glyph name without changing its stored identity."""
    selected_locale = locale or str(get_settings().general.language)
    catalogs = (_load_catalog(selected_locale)[kind], _load_catalog("enUS")[kind])

    resolved_id = identifier if identifier and any(identifier in catalog for catalog in catalogs) else ""
    normalized_source = _normalize(source_name)
    if not resolved_id and kind == "boards" and normalized_source in _START_ALIASES:
        resolved_id = _starting_board_id(class_slug)
    if not resolved_id:
        resolved_id = _name_index(kind).get(normalized_source, "")

    for catalog in catalogs:
        if resolved_id in catalog:
            return catalog[resolved_id]

    return str(source_name or "").strip()


__all__ = ["localized_paragon_name", "paragon_class_slug"]
