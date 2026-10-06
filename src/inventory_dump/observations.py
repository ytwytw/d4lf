"""Catalog-independent facts explicitly present in item accessibility text."""

import re
from typing import TYPE_CHECKING

from src.inventory_dump.framing import is_literal_item_header

if TYPE_CHECKING:
    from src.type_aliases import JsonObject

_PLAYER_ANNOUNCEMENT = re.compile(r"^.+?\s+\|\s+\d{1,3}\s+\(\d+\)(?:\s+\(\d+\))?$")
_SYSTEM_ANNOUNCEMENTS = frozenset({"电池充电中", "电池放电中"})
_NAME_FLAG = re.compile(r"^\[(?:FAVORITED ITEM|MARKED AS JUNK|收藏物品|标记为垃圾)\]\.\s*", re.IGNORECASE)
_FAVORITE_NAME = re.compile(r"^\[(?:FAVORITED ITEM|收藏物品)\]\.\s*", re.IGNORECASE)
_POWER = re.compile(r"^(\d[\d,]*)\s*(?:物品强度|Item Power)\b", re.IGNORECASE)
_LEVEL = re.compile(r"(?:需要等级|Required Level|Requires Level)\s*[:：]?\s*(\d+)", re.IGNORECASE)
_QUANTITY = re.compile(r"^(?:数量|堆叠数量|Quantity|Stack Size)\s*[:：]\s*(\d[\d,]*)", re.IGNORECASE)
_PRICE = re.compile(r"(?:出售价格|Sell Value|Sell Price)\s*[:：]\s*(\d[\d,]*)", re.IGNORECASE)
_DURABILITY = re.compile(r"(?:耐久度|Durability)\s*[:：]\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_TEMPERING = re.compile(r"(?:回火|Tempering)\s*[:：]\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_QUALITY = re.compile(r"^(\d+)\s*[（(]\s*\+(\d+)\s*[）)]\s*(?:品质|Quality)$", re.IGNORECASE)


def ambient_only(lines: list[str]) -> bool:
    """Recognize proven non-item broadcasts, never discard unknown item-looking text."""
    return bool(lines) and all(
        line.strip() in _SYSTEM_ANNOUNCEMENTS or _PLAYER_ANNOUNCEMENT.fullmatch(line.strip()) for line in lines
    )


def observe_favorite(lines: list[str]) -> JsonObject | None:
    """Only an explicit current-title marker confirms favorite; absence stays unknown."""
    if not lines or not (marker := _FAVORITE_NAME.match(lines[0])):
        return None
    name = lines[0][marker.end() :].strip()
    if not name or _NAME_FLAG.match(name):
        return None
    return {"source": "raw_tts_title", "verification": "explicit_marker", "value": True, "text": lines[0]}


def _number(pattern: re.Pattern[str], lines: list[str]) -> int | None:
    for line in lines:
        if match := pattern.search(line):
            return int(match[1].replace(",", ""))
    return None


def _ratio(pattern: re.Pattern[str], lines: list[str]) -> JsonObject | None:
    for line in lines:
        if match := pattern.search(line):
            return {"numerator": int(match[1]), "denominator": int(match[2]), "text": match[0]}
    return None


def _quality(lines: list[str]) -> JsonObject | None:
    for line in lines:
        if match := _QUALITY.fullmatch(line.strip()):
            return {"value": int(match[1]), "bonus": int(match[2]), "text": line}
    return None


def observe_item_fields(lines: list[str]) -> JsonObject:
    """Extract literal facts without resolving names, stat IDs, affix classes or socket contents."""
    requirements = [line for line in lines if _LEVEL.search(line)]
    empty_sockets = [line for line in lines if line.strip().lower() in {"空插槽", "empty socket"}]
    quantity = _number(_QUANTITY, lines)
    # Verified stackable-item titles show the stack size; absence does not prove one.
    if (
        quantity is None
        and len(lines) > 1
        and is_literal_item_header(lines[1])
        and (match := re.search(r"\((\d[\d,]*)\)\s*$", lines[0]))
    ):
        quantity = int(match[1].replace(",", ""))
    return {
        "source": "raw_tts",
        "catalog_mapped": False,
        "name_text": _NAME_FLAG.sub("", lines[0]).strip() if lines else None,
        "type_text": lines[1].strip() if len(lines) > 1 else None,
        "item_power": _number(_POWER, lines),
        "quality": _quality(lines),
        "quantity": quantity,
        "required_level": _number(_LEVEL, lines),
        "requirements_text": requirements,
        "binding_text": [line for line in lines if re.search(r"绑定|Bound", line, re.IGNORECASE)],
        "modifier_lines": [line for line in lines[2:] if re.match(r"^(?:[+x×]\s*\d|\d[\d,.]*\s*%)", line)],
        "description_lines": lines[2:],
        "empty_socket_mentions": len(empty_sockets),
        "empty_socket_text": empty_sockets,
        "sell_value": _number(_PRICE, lines),
        "durability": _ratio(_DURABILITY, lines),
        "tempering": _ratio(_TEMPERING, lines),
        "limitations": [
            "Literal text observations only; names and affixes have not been mapped to catalog identifiers.",
            "Missing fields are unknown. Empty-socket mentions do not establish the total number of sockets.",
            "Modifier text does not distinguish inherent, random, tempered or masterworked affixes.",
        ],
    }
