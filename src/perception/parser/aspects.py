"""Resolve a shared Chinese aspect label only from its complete, same-tooltip effect."""

import re
from typing import TYPE_CHECKING

from src.locale_data import normalize_locale_text

if TYPE_CHECKING:
    from src.game_data import GameCatalog

# Fixed bilingual Description templates for the distinct malicious and virulent aspect identities.
# These are full Description templates, not keyword heuristics or claims about current drops.
_DESCRIPTIONS = {
    "malicious": "处于恶魔形态时，近距范围内每有一名恶魔或敌人，你造成的伤害就会提高 #%，最多提高 #%。",
    "virulent": (
        "狂犬撕咬感染敌人后，其冷却时间缩短 # 秒。当感染对象为精英敌人时，冷却时间缩减变为原来的三倍。"
        "此外，你对受到狂犬撕咬影响的敌人额外造成 #% 增伤伤害。"
    ),
}
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_RANGE = rf"\[{_NUMBER}(?:-{_NUMBER})?\]"
_VALUE = rf"(?:{_NUMBER}(?:{_RANGE})?|{_RANGE})"
_MARKER = r"(?:\[x\]|x|\[\+\]|\+)?"
_PERCENT = rf"{_MARKER}{_VALUE}%(?:{_RANGE}%?)?{_MARKER}"


def _compact(text: str) -> str:
    return "".join(normalize_locale_text(text).split())


def _effect_pattern(description: str) -> re.Pattern[str]:
    pattern = re.escape(_compact(description)).replace(r"\#%", _PERCENT).replace(r"\#", _VALUE)
    return re.compile(r"(?:已刻印:|刻印:)?" + pattern)


_EFFECTS = {canonical: _effect_pattern(description) for canonical, description in _DESCRIPTIONS.items()}


def _resolve_shared_aspect(text: str, name: str, catalog: GameCatalog) -> str | None:
    if catalog.grammar.locale != "zhCN":
        return None
    normalized_name = normalize_locale_text(name)
    matches = [
        (len(alias), canonical)
        for canonical, display in catalog.aspect_dict.items()
        if (alias := normalize_locale_text(display)) and alias in normalized_name
    ]
    longest = max((length for length, _ in matches), default=0)
    candidates = {canonical for length, canonical in matches if length == longest}
    if candidates != _DESCRIPTIONS.keys():
        return None
    effects = [canonical for canonical, pattern in _EFFECTS.items() if pattern.fullmatch(_compact(text))]
    return effects[0] if len(effects) == 1 else None


def _reject_conflicting_shared_aspect_effects(
    tts_section: list[str], aspect_index: int, name: str | None, catalog: GameCatalog
) -> None:
    if name is None or (current := _resolve_shared_aspect(tts_section[aspect_index], name, catalog)) is None:
        return
    for line in tts_section[aspect_index + 1 :]:
        if catalog.grammar.contains("item_end_control", line):
            break
        if any(canonical != current and pattern.fullmatch(_compact(line)) for canonical, pattern in _EFFECTS.items()):
            msg = "Conflicting legendary aspect effects in the current tooltip"
            raise ValueError(msg)
