"""Detect navigation controls from observed icons, not configured stash counts."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from src.inventory_dump.templates import icon

if TYPE_CHECKING:
    from src.automation import ItemSlot

INVENTORY_PAGES = ("equipment", "talisman", "socketables", "consumables", "keys")
REQUIRED_EQUIPMENT_SLOTS = frozenset({"head", "chest", "gloves", "legs", "boots", "amulet", "ring_upper", "ring_lower"})
EQUIPMENT_SLOTS = (
    ("head", 1497, 122),
    ("chest", 1497, 216),
    ("gloves", 1497, 312),
    ("legs", 1497, 405),
    ("boots", 1497, 496),
    ("weapon_left", 1497, 598),
    ("amulet", 1861, 214),
    ("ring_upper", 1861, 309),
    ("ring_lower", 1861, 404),
    ("weapon_right_inner", 1807, 610),
    ("weapon_right", 1865, 610),
    ("weapon_center_left", 1652, 609),
    ("weapon_center_right", 1708, 609),
)
TALISMAN_SLOTS = (
    ("charm_top", 1563, 234),
    ("charm_top_right", 1696, 307),
    ("charm_bottom_right", 1696, 455),
    ("charm_bottom", 1563, 533),
    ("charm_bottom_left", 1432, 457),
    ("charm_top_left", 1430, 311),
    ("seal", 1567, 389),
)


@dataclass(frozen=True, slots=True)
class TabTarget:
    name: str
    center: tuple[int, int]
    confidence: float
    icon_recognized: bool = True


def scale_point(image: np.ndarray, x: float, y: float, *, right: bool = False) -> tuple[int, int]:
    """Convert the 1080p reference to physical pixels of the supplied unscaled capture."""
    height, width = (int(value) for value in image.shape[:2])
    scale = height / 1080
    return round(width - (1920 - x) * scale if right else x * scale), round(y * scale)


def _region(image: np.ndarray, box: tuple[int, int, int, int], *, right: bool) -> tuple[np.ndarray, int, int]:
    x1, y1 = scale_point(image, box[0], box[1], right=right)
    x2, y2 = scale_point(image, box[2], box[3], right=right)
    return image[max(0, y1) : y2, max(0, x1) : x2], max(0, x1), max(0, y1)


def find_tabs(image: np.ndarray, *, stash: bool = False) -> list[TabTarget]:
    """Only controls whose icons match the captured game UI become click targets."""
    area, offset_x, offset_y = _region(image, (20, 125, 670, 211) if stash else (1230, 669, 1900, 720), right=not stash)
    if area.size == 0:
        return []
    gray = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY)
    scale = image.shape[0] / 1080
    found: list[TabTarget] = []
    for name in ("stash",) if stash else INVENTORY_PAGES:
        reference = cv2.resize(icon(name), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = reference.shape
        if h > gray.shape[0] or w > gray.shape[1]:
            continue
        scores = cv2.matchTemplate(gray, reference, cv2.TM_CCOEFF_NORMED)
        while True:
            _, score, _, point = cv2.minMaxLoc(scores)
            if score < 0.68:
                break
            x, y = point
            found.append(TabTarget(name, (offset_x + x + w // 2, offset_y + y + h // 2), score))
            scores[max(0, y - h) : y + h, max(0, x - w) : x + w] = -1
            if not stash:
                break
    found.sort(key=lambda tab: tab.center[0])
    if stash:
        found = _stash_frames(gray, scale, offset_x, offset_y, found)
    return found


def _stash_frames(
    gray: np.ndarray, scale: float, offset_x: int, offset_y: int, icons: list[TabTarget]
) -> list[TabTarget]:
    reference = cv2.resize(icon("stash_frame"), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = reference.shape
    if h > gray.shape[0] or w > gray.shape[1]:
        return []
    scores = cv2.matchTemplate(gray, reference, cv2.TM_CCOEFF_NORMED)
    frames = list(icons)
    while True:
        _, score, _, point = cv2.minMaxLoc(scores)
        if score < 0.76:
            break
        x, y = point
        center = (offset_x + x + w // 2, offset_y + y + round(24 * scale))
        if not any(abs(tab.center[0] - center[0]) < 22 * scale for tab in frames):
            frames.append(TabTarget("unknown", center, score, icon_recognized=False))
        scores[max(0, y - round(20 * scale)) : y + round(20 * scale), max(0, x - w) : x + w] = -1
    frames.sort(key=lambda tab: tab.center[0])
    return [
        TabTarget(str(index), tab.center, tab.confidence, tab.icon_recognized)
        for index, tab in enumerate(frames, start=1)
    ]


def tab_selected(image: np.ndarray, target: TabTarget) -> bool:
    scale = image.shape[0] / 1080
    x, y = target.center
    half_w, half_h = round(23 * scale), round(19 * scale)
    area = image[max(0, y - half_h) : y + half_h, max(0, x - half_w) : x + half_w]
    if not area.size:
        return False
    blue, green, red = cv2.split(area.astype(np.float32))
    return float(np.mean((red > 75) & (red > green * 1.5) & (red > blue * 1.5))) > 0.08


def equipment_targets(image: np.ndarray, *, talisman: bool = False) -> list[tuple[str, tuple[int, int]]]:
    """Named slots come from the existing D4LF layout and captured equipment panels."""
    points = TALISMAN_SLOTS if talisman else EQUIPMENT_SLOTS
    targets = []
    for name, x, y in points:
        center = scale_point(image, x, y, right=True)
        if talisman or _has_slot_frame(image, center):
            targets.append((name, center))
    return targets


def _has_slot_frame(image: np.ndarray, center: tuple[int, int]) -> bool:
    """Exclude weapon positions without a slot on the current character layout."""
    scale = image.shape[0] / 1080
    x, y = center
    half_w, half_h = round(40 * scale), round(52 * scale)
    area = image[max(0, y - half_h) : y + half_h, max(0, x - half_w) : x + half_w]
    if not area.size:
        return False
    edges = cv2.Canny(area, 45, 110)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(12, round(24 * scale)),
        minLineLength=round(45 * scale),
        maxLineGap=round(8 * scale),
    )
    if lines is None:
        return False
    vertical = [
        (int(x1) + int(x2)) / 2 for x1, _y1, x2, _y2 in lines.reshape(-1, 4) if abs(int(x1) - int(x2)) < 4 * scale
    ]
    # Several lines on one edge can belong to an adjacent weapon or the character model.
    return any(x < half_w - 12 * scale for x in vertical) and any(x > half_w + 12 * scale for x in vertical)


# Grey-level change per slot below which consecutive captures count as the same frame.
ICON_SETTLE_TOLERANCE = 4.0
GridSignature = dict[tuple[int, int], tuple[bool, float]]


def grid_signature(image: np.ndarray, occupied: list[ItemSlot], empty: list[ItemSlot]) -> GridSignature:
    """Per-slot occupancy guess and mean level, only used to see that fading icons have stopped changing."""
    signature: GridSignature = {}
    for slot, is_occupied in [*((slot, True) for slot in occupied), *((slot, False) for slot in empty)]:
        x, y, w, h = slot.bounding_box
        area = image[max(0, y) : y + h, max(0, x) : x + w]
        signature[slot.center] = (is_occupied, float(np.mean(area)) if area.size else 0.0)
    return signature


def grid_settled(previous: GridSignature, current: GridSignature) -> bool:
    return previous.keys() == current.keys() and all(
        previous[center][0] == state and abs(previous[center][1] - level) <= ICON_SETTLE_TOLERANCE
        for center, (state, level) in current.items()
    )
