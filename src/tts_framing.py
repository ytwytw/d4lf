from __future__ import annotations

import enum
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.locale_data import LocaleGrammar

_MAX_CACHED_LINES = 500


class ItemIdentifiers(enum.Enum):
    COMPASS = "Compass"
    ESCALATION_SIGIL = "Escalation Sigil"
    NIGHTMARE_SIGIL = "Nightmare Sigil"
    TRIBUTE = "TRIBUTE OF"
    WHISPERING_KEY = "WHISPERING KEY"


def find_item_start(data: list[str], *, grammar: LocaleGrammar, catalog) -> int | None:
    for index, item in reversed(list(enumerate(data))):
        if grammar.contains("item_start_ignored", item):
            continue

        if any(grammar.identifier_matches(identifier.name, item, mode="startswith") for identifier in ItemIdentifiers):
            return index

        cleaned_str = re.sub(r"[^A-Za-z]", "", item)
        if len(cleaned_str) >= 3 and item.isupper():
            return index

        if index + 1 < len(data):
            header = grammar.strip_terms(data[index + 1], "ancestral", "bloodied")
            rarity_name = grammar.rarity_name(header)
            item_type_text = grammar.strip_rarity(header, rarity_name) if rarity_name else header
            has_item_power = any(grammar.contains("item_power", line) for line in data[index + 2 :])
            if catalog.resolve_item_type(item_type_text) and (rarity_name or has_item_power):
                return index

    return None


class TtsFramer:
    """Turn raw accessibility lines into bounded, replayable item traces."""

    def __init__(self, grammar: LocaleGrammar, catalog, *, max_lines: int = _MAX_CACHED_LINES):
        self.grammar = grammar
        self.catalog = catalog
        self.max_lines = max_lines
        self.lines: list[str] = []
        self.raw_lines: list[str] = []
        self.last_raw_item: list[str] = []

    def feed(self, data: str, *, raw_data: str | None = None) -> list[str] | None:
        self.lines.append(data)
        self.raw_lines.append(data if raw_data is None else raw_data)
        if len(self.lines) > self.max_lines:
            overflow = len(self.lines) - self.max_lines
            del self.lines[:overflow]
            del self.raw_lines[:overflow]
        if not self.grammar.contains("item_end_control", data):
            return None
        start = find_item_start(self.lines, grammar=self.grammar, catalog=self.catalog)
        if start is None:
            return None
        item = self.lines[start:]
        self.last_raw_item = self.raw_lines[start:]
        self.lines = []
        self.raw_lines = []
        return item


def fix_data(data: str, *, grammar: LocaleGrammar | None = None) -> str:
    to_remove = ["&apos;", "&quot;", "[FAVORITED ITEM]. ", "\uffc2\uffa0", "(Spiritborn Only)", "[MARKED AS JUNK]. "]

    if grammar is not None:
        to_remove.extend(grammar.terms("item_name_prefix"))

    for item in to_remove:
        data = data.replace(item, "")

    return data.strip()
