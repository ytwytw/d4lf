import enum
import re
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.locale_data import LocaleGrammar

_MAX_CACHED_LINES = 500


class ItemIdentifier(enum.Enum):
    COMPASS = enum.auto()
    ESCALATION_SIGIL = enum.auto()
    NIGHTMARE_SIGIL = enum.auto()
    TRIBUTE = enum.auto()
    WHISPERING_KEY = enum.auto()


class ItemTypeCatalog(Protocol):
    def resolve_item_type(self, value: str) -> str | None: ...


def find_item_start(data: list[str], *, grammar: LocaleGrammar, catalog: ItemTypeCatalog) -> int | None:
    for index, item in reversed(list(enumerate(data))):
        if grammar.contains("item_start_ignored", item):
            continue

        if any(grammar.identifier_matches(identifier.name, item, mode="startswith") for identifier in ItemIdentifier):
            return index

        cleaned_text = re.sub(r"[^A-Za-z]", "", item)
        if len(cleaned_text) >= 3 and item.isupper():
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

    def __init__(self, grammar: LocaleGrammar, catalog: ItemTypeCatalog, *, max_lines: int = _MAX_CACHED_LINES):
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
    tokens = ["&apos;", "&quot;", "[FAVORITED ITEM]. ", "\uffc2\uffa0", "(Spiritborn Only)", "[MARKED AS JUNK]. "]
    if grammar is not None:
        tokens.extend(grammar.terms("item_name_prefix"))
    for token in tokens:
        data = data.replace(token, "")
    return data.strip()
