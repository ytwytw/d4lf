"""Unique profile-editor labels for canonical identities that share localized text."""

import logging
from collections import Counter
from functools import cache
from typing import TYPE_CHECKING

from src.game_data import GameCatalog
from src.game_data.localized_maps import load_string_map
from src.settings import BASE_DIR

if TYPE_CHECKING:
    from collections.abc import Mapping

LOGGER = logging.getLogger(__name__)
_AFFIX_FILES = ("affixes.json", "charms_affixes.json", "seals_affixes.json")
_PRECISION_HINTS = {
    "zhCN": {"integer": "整数范围", "decimal": "小数范围"},
    "enUS": {"integer": "integer range", "decimal": "decimal range"},
}
# Short summaries of the reviewed in-game descriptions the parser matches (tribute item SNO 2077993 / 2090358).
_TRIBUTE_HINTS = {"zhCN": {"tribute_of_heritage": "职业专属暗金物品", "tribute_of_titans": "巢穴首领秘宝钥匙"}}


@cache
def _english_labels(*file_names: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for file_name in file_names:
        try:
            labels.update(load_string_map(BASE_DIR / "assets" / "lang" / "enUS" / file_name))
        except OSError, ValueError:
            LOGGER.warning("English labels unavailable for %s; colliding rows show canonical identities", file_name)
    return labels


def disambiguate(labels: Mapping[str, str], details: Mapping[str, str], locale: str = "enUS") -> dict[str, str]:
    """Return canonical -> label, changing only labels that are shared by several identities."""
    counts = Counter(labels.values())
    template = "{label}（{detail}）" if locale == "zhCN" else "{label} ({detail})"
    result = {
        canonical: template.format(label=label, detail=details.get(canonical) or canonical)
        if counts[label] > 1
        else label
        for canonical, label in labels.items()
    }
    # A detail can itself collide; the canonical identity is always unique.
    final = Counter(result.values())
    return {canonical: f"{label} [{canonical}]" if final[label] > 1 else label for canonical, label in result.items()}


def affix_labels(affixes: Mapping[str, str], catalog: GameCatalog | None = None) -> dict[str, str]:
    catalog = catalog or GameCatalog()
    locale = catalog.grammar.locale
    words = _PRECISION_HINTS.get(locale, _PRECISION_HINTS["enUS"])
    precision = {
        canonical: words[kind]
        for mapping in catalog.grammar.affix_range_precision.values()
        for kind, canonical in mapping.items()
        if kind in words
    }
    english = _english_labels(*_AFFIX_FILES)
    details = {
        canonical: " · ".join(part for part in (english.get(canonical), precision.get(canonical)) if part)
        for canonical in affixes
    }
    return disambiguate(affixes, details, locale)


def tribute_labels(catalog: GameCatalog | None = None) -> dict[str, str]:
    catalog = catalog or GameCatalog()
    locale = catalog.grammar.locale
    english = _english_labels("tributes.json")
    hints = _TRIBUTE_HINTS.get(locale, {})
    details = {
        canonical: " · ".join(part for part in (english.get(canonical), hints.get(canonical)) if part)
        for canonical in catalog.tribute_dict
    }
    return disambiguate(catalog.tribute_dict, details, locale)


__all__ = ["affix_labels", "disambiguate", "tribute_labels"]
