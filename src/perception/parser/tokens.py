"""Shared tooltip patterns and boundaries, independent of item assembly."""

import re

from src.game_data import GameCatalog

_AFFIX_RE = re.compile(
    r"(?P<affixvalue1>[0-9]+(?:\.[0-9]+)?)[^0-9]+\[(?P<minvalue1>[0-9]+(?:\.[0-9]+)?)"
    r" - (?P<maxvalue1>[0-9]+(?:\.[0-9]+)?)]|"
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
    return any(line.lower().startswith(marker) for marker in _AFFIX_STOP_MARKERS) or GameCatalog().grammar.startswith(
        "affix_stop", line
    )
