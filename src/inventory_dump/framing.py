"""Literal dump framing for observed item headers unsupported by the filtering parser."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.perception import RawTtsEvent

_ITEM_HEADER = re.compile(
    r"^(?:(?:神话暗金|暗金|传奇|稀有|魔法|普通)\s*)?(?:仪祭符文|祈告符文|灵魂尖刺)$"
    r"|^暗金战利品$"
    r"|^(?:(?:Mythic Unique|Unique|Legendary|Rare|Magic|Common)\s+)?(?:Rune of Ritual|Rune of Invocation)$",
    re.IGNORECASE,
)
# Literal titles observed in the game's Chinese accessibility text. Keep this
# finite: a short UI label or prose mentioning an item type is not an item frame.
_LITERAL_HEADERS = frozenset({
    "宝石",
    "暗金消耗品",
    "传奇消耗品",
    "稀有消耗品",
    "魔法消耗品",
    "稀有首领战利品",
    "神话巢穴首领钥匙",
    "暗金巢穴首领钥匙",
    "传奇巢穴首领钥匙",
    "稀有巢穴首领钥匙",
    "传奇升级符印",
    "稀有梦魇纪事",
    "传奇炼狱魔潮罗盘",
})
_END_CONTROLS = frozenset({"鼠标右键", "right mouse button", "right click"})


def is_literal_item_header(text: str) -> bool:
    header = text.strip()
    return header in _LITERAL_HEADERS or _ITEM_HEADER.fullmatch(header) is not None


def extract_literal_trace(events: list[RawTtsEvent]) -> list[RawTtsEvent] | None:
    """Require an observed name, exact type header and footer within this hover attempt."""
    for index in range(1, len(events)):
        if not is_literal_item_header(events[index].text):
            continue
        name = events[index - 1].text.strip()
        if not name or "|" in name or name.lower() in _END_CONTROLS:
            continue
        for end in range(index + 1, len(events)):
            if is_literal_item_header(events[end].text):
                break
            if events[end].text.strip().lower() in _END_CONTROLS:
                return events[index - 1 : end + 1]
    return None
