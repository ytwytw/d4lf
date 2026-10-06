"""Disambiguate shared tribute names using only the current item's complete description."""

import re
from typing import TYPE_CHECKING

from src.locale_data import normalize_locale_text

if TYPE_CHECKING:
    from src.game_data import GameCatalog

# Item SNO 2077993 / 2090358; see the fixed-source Chinese tribute research.
_DESCRIPTIONS = {
    "tribute_of_heritage": (
        "所有难度均可使用。向幽暗之城中的灵焰火盆进献贡品，以此来丰富地下城奖励。"
        "如果在完成地下城时至少达到了调谐级别 1，则可获得职业专属的暗金物品。"
    ),
    "tribute_of_titans": (
        "向幽暗之城中的灵焰火盆进献贡品来丰富奖励：达到调谐级别 1 可获得巢穴首领秘宝钥匙。仅在折磨难度可用。"
    ),
}
_SHARED_NAME = "巨人贡品"


def _description_key(text: str) -> str:
    # TTS inserts ASCII full stops between rendered tooltip paragraphs.
    normalized = normalize_locale_text(text)
    normalized = re.sub(r"(?<=[:。])\s*\.(?=\s|$)", "", normalized)
    return "".join(normalized.split())


_EFFECTS = {_description_key(description): canonical for canonical, description in _DESCRIPTIONS.items()}


def _resolve_tribute_from_tts(tts_item: list[str], header_name: str, catalog: GameCatalog) -> str | None:
    names = {re.sub(r"\s*\([0-9,]+\)$", "", normalize_locale_text(tts_item[0])), normalize_locale_text(header_name)}
    if catalog.grammar.locale != "zhCN" or _SHARED_NAME not in names:
        return catalog.resolve_tribute(tts_item[0]) or catalog.resolve_tribute(header_name)
    candidates = {
        canonical
        for canonical, display in catalog.tribute_dict.items()
        if normalize_locale_text(display) == _SHARED_NAME
    }
    if names != {_SHARED_NAME} or candidates != _DESCRIPTIONS.keys() or len(tts_item) < 3:
        return None
    canonical = _EFFECTS.get(_description_key(tts_item[2]))
    if canonical is None:
        return None
    for line in tts_item[3:]:
        if catalog.grammar.contains("item_end_control", line):
            break
        if _description_key(line) in _EFFECTS:
            return None
    return canonical
