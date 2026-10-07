"""Exact affix identity for build importers.

A source stat names a D4LF affix only when, after removing value and markup formatting, its text equals one
known English label or canonical key. Unknown or ambiguous text resolves to ``None`` so the importer counts it as
unresolved and broadens the rule, instead of a similarity match silently requiring a different affix.
"""

import re
from functools import cache

from src.game_data import ItemType
from src.importing.source_locale import source_affix_dict_for_item_type
from src.locale_data import normalize_locale_text

SOURCE_LOCALE = "enUS"
# Only formatting is removed; any other braces, brackets or parentheses keep their words, so an unrecognized
# qualifier makes the text unknown rather than shortening it to a different affix.
_MARKUP = re.compile(r"\{(?:/?c(?:_\w+|:\w+)?|/?[uib]|icon:[^{}]*|value\d*|s\d+)\}")  # maxroll tags, placeholders
_MULTIPLIER_MARK = re.compile(r"(?<![a-z])x(?=\s*[\[\d+])")  # "x[...]" / "x12%" multiplicative value prefix
# A bracket is removed only when all of it is value syntax: a number or range, a maxroll value expression
# (snake_case attribute names or calls, numbers and arithmetic) with its format, or an x/+ marker. A bracket
# holding any plain word, with or without digits or "|", keeps its words.
_NUMBER = r"[+-]?\d+(?:[.,]\d+)*\s*%?"
_CODE = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+|[a-z][a-z0-9_]*(?=\()"  # "affix_value_1", "maxstacks(...)"
_VALUE = re.compile(
    rf"\[\s*{_NUMBER}\s*(?:[-~]\s*{_NUMBER}\s*)?\]"  # "[1,226 - 1,450]", "[11.0 - 15.0]", "[5%]"
    rf"|\[(?>\s+|{_NUMBER}|{_CODE}|[-+*/(),])*+\|[\d%x+~.\s]*\|\]"  # "[{value}*100|%|]", "[affix_value_1||]"
    r"|\[[x+]\\?\]"  # "[x]" multiplier and "[+]" sign markers (maxroll escapes them as "[x\]")
)
_PLURAL = re.compile(r"\|\d*[^:|;]*:([^:|;]*);")  # maxroll plural template "|4Charge:Charges;"
_PARENTHETICAL = re.compile(r"\([^()]*(?:\)|$)")
# Words left in a parenthetical that only qualifies the number: "(5% at level 70)", "(to a minimum of 2)".
_VALUE_QUALIFIERS = frozenset({"", "at level", "to a minimum of"})
_NOT_WORD = re.compile(r"[\W\d_]+")


def _words(text: str) -> str:
    # Labels drop apostrophes and join hyphenated words ("nonphysical", "bulkathos pride"), as the in-game parser does.
    text = text.replace("'", "").replace("\u2019", "").replace("-", "")
    return " ".join(_NOT_WORD.sub(" ", text).split())


def _drop_value_qualifier(match: re.Match[str]) -> str:
    return " " if _words(match.group(0)) in _VALUE_QUALIFIERS else match.group(0)


def normalize_affix_label(text: str) -> str:
    """Strip value and markup formatting only; words, and therefore meaning, are kept as written."""
    text = _MULTIPLIER_MARK.sub(" ", normalize_locale_text(_MARKUP.sub(" ", text)))
    text = _PLURAL.sub(r"\1", _VALUE.sub(" ", text))
    return _words(_PARENTHETICAL.sub(_drop_value_qualifier, text))


@cache
def _exact_index(item_type: ItemType | None) -> dict[str, str | None]:
    """Normalized label or key -> canonical name; ``None`` marks text shared by different affixes."""
    index: dict[str, str | None] = {}
    for canonical, display in source_affix_dict_for_item_type(item_type, SOURCE_LOCALE).items():
        for text in {normalize_affix_label(display), normalize_affix_label(canonical)}:
            if text:
                index[text] = canonical if index.get(text, canonical) == canonical else None
    return index


def _resolve_one(index: dict[str, str | None], candidates: list[str]) -> str | None:
    found = {index[text] for text in candidates if text in index}
    return found.pop() if len(found) == 1 and None not in found else None


def resolve_affix(text: str, item_type: ItemType | None) -> str | None:
    """Canonical affix named exactly by ``text`` for this item type, or ``None`` when unknown or ambiguous."""
    normalized = normalize_affix_label(text)
    return _resolve_one(_exact_index(item_type), [normalized]) if normalized else None


def resolve_seal_affix(text: str, guessed_set_name: str | None = None) -> str | None:
    """Seal affix for a stat that may belong to the build's guessed charm set.

    Sources list set seal stats without the set name, so the stat is tried both as written and under the
    guessed set; a stat that names a generic affix and a different set affix alike stays unresolved.
    """
    stat = normalize_affix_label(text)
    if not stat:
        return None
    candidates = [stat]
    if guessed_set_name:
        candidates.append(f"{normalize_affix_label(guessed_set_name)} {stat}")
    return _resolve_one(_exact_index(ItemType.HoradricSeal), candidates)


__all__ = ["normalize_affix_label", "resolve_affix", "resolve_seal_affix"]
