from copy import copy
from typing import TYPE_CHECKING

from src.config.ui import ResManager
from src.item.data.rarity import ItemRarity
from src.template_finder import SearchResult, TemplateMatch, search
from src.utils.image_operations import crop
from src.utils.roi_operations import fit_roi_to_window_size

if TYPE_CHECKING:
    import numpy as np

map_template_rarity = {
    "item_common_top_left": ItemRarity.Common,
    "item_leg_top_left": ItemRarity.Legendary,
    "item_magic_top_left": ItemRarity.Magic,
    "item_mythic_top_left": ItemRarity.Mythic,
    "item_rare_top_left": ItemRarity.Rare,
    "item_unique_top_left": ItemRarity.Unique,
}

SHORT_SEPARATOR_REFS = ["item_seperator_short_rare", "item_seperator_short_legendary", "item_seperator_short_mythic"]


def _choose_best_result(res_left: SearchResult, res_right: SearchResult) -> SearchResult:
    left_has_match = res_left.success and bool(res_left.matches)
    right_has_match = res_right.success and bool(res_right.matches)
    if left_has_match and not right_has_match:
        return res_left
    if right_has_match and not left_has_match:
        return res_right
    if left_has_match and right_has_match:
        return res_left if res_left.matches[0].score > res_right.matches[0].score else res_right
    return SearchResult(success=False)


def _template_search(img: np.ndarray, anchor: int, roi: np.ndarray, take_debug_screenshot: bool = False):
    roi_copy = copy(roi)
    roi_copy[0] += anchor
    ok, roi_left = fit_roi_to_window_size(roi_copy, ResManager().pos.window_dimensions)
    if ok:
        return search(
            ref=list(map_template_rarity.keys()),
            inp_img=img,
            roi=roi_left,
            threshold=0.8,
            mode="all",
            take_debug_screenshot=take_debug_screenshot,
        )
    return SearchResult(success=False)


def _separator_search(img: np.ndarray, anchor: int, rel_roi: np.ndarray) -> list[TemplateMatch]:
    """Find tooltip separators close to the expected left or right tooltip edge."""
    roi = copy(rel_roi)
    roi[0] += anchor
    roi[2] = ResManager().offsets.item_descr_width
    ok, fitted_roi = fit_roi_to_window_size(roi, ResManager().pos.window_dimensions)
    if not ok:
        return []

    result = search(
        ref=SHORT_SEPARATOR_REFS,
        inp_img=img,
        roi=fitted_roi,
        threshold=0.8,
        use_grayscale=True,
        mode="all",
        do_multi_process=False,
    )
    if not result.success:
        return []

    # The separator begins just inside the tooltip edge. Reject matches farther
    # across the expanded ROI, which are usually separators from another panel.
    maximum_offset = max(100, ResManager().offsets.item_descr_width // 2)
    return [match for match in result.matches if match.region[0] <= fitted_roi[0] + maximum_offset]


def _crop_from_separator(img: np.ndarray, separator: TemplateMatch) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    offsets = ResManager().offsets
    item_descr_pad = offsets.item_descr_pad
    item_descr_width = offsets.item_descr_width
    window_width, window_height = ResManager().pos.window_dimensions

    # Current D4 tooltip corner art changes with rarity, favorite/junk state,
    # and season. The first short separator is much more stable. Six line
    # heights leaves enough room for every observed name/type/power header.
    outer_x = max(0, separator.region[0] - item_descr_pad)
    outer_y = max(0, separator.region[1] - 6 * offsets.item_descr_line_height)
    crop_x = max(0, outer_x + item_descr_pad)
    crop_y = max(0, outer_y + item_descr_pad)
    crop_width = min(item_descr_width - 2 * item_descr_pad, window_width - crop_x)

    search_roi = (outer_x, outer_y, min(item_descr_width, window_width - outer_x), window_height - outer_y)
    crop_height = window_height - (2 * offsets.item_descr_off_bottom_edge) - outer_y
    bottom_result = search(
        ref=["item_bottom_edge"], inp_img=img, roi=search_roi, threshold=0.54, use_grayscale=True, mode="all"
    )
    if bottom_result.success:
        bottom_edge = max(bottom_result.matches, key=lambda candidate: candidate.center[1])
        detected_height = bottom_edge.center[1] - offsets.item_descr_off_bottom_edge - outer_y
        if detected_height > 0:
            crop_height = detected_height

    crop_height = min(crop_height, window_height - crop_y)
    crop_roi = (crop_x, crop_y, crop_width, crop_height)
    return crop(img, crop_roi), crop_roi


def _find_descr_from_separator(
    img: np.ndarray, anchor: tuple[int, int], expected_rarity: ItemRarity
) -> tuple[bool, ItemRarity | None, np.ndarray | None, tuple[int, int, int, int] | None]:
    matches = _separator_search(img, anchor[0], ResManager().roi.rel_descr_search_left)
    matches += _separator_search(img, anchor[0], ResManager().roi.rel_descr_search_right)
    if not matches:
        return False, None, None, None

    # A tooltip may contain a second separator near its footer. The first one
    # divides the item header from the affixes and is the stable crop anchor.
    separator = min(matches, key=lambda match: (match.center[1], -match.score))
    cropped_descr, crop_roi = _crop_from_separator(img, separator)
    return True, expected_rarity, cropped_descr, crop_roi


def find_descr(
    img: np.ndarray, anchor: tuple[int, int], expected_rarity: ItemRarity | None = None
) -> tuple[bool, ItemRarity | None, np.ndarray | None, tuple[int, int, int, int] | None]:
    if expected_rarity is not None:
        separator_result = _find_descr_from_separator(img, anchor, expected_rarity)
        if separator_result[0]:
            return separator_result

    item_descr_width = ResManager().offsets.item_descr_width
    item_descr_pad = ResManager().offsets.item_descr_pad
    _, window_height = ResManager().pos.window_dimensions

    res_left = _template_search(img, anchor[0], ResManager().roi.rel_descr_search_left)
    res_right = _template_search(img, anchor[0], ResManager().roi.rel_descr_search_right)

    res = _choose_best_result(res_left, res_right)

    if res.success and res.matches:
        match = res.matches[0]
        rarity = map_template_rarity[match.name.lower()]
        # find equipe template
        offset_top = int(window_height * 0.03)
        roi_y = match.region[1] + offset_top
        search_height = window_height - roi_y - offset_top
        delta_x = int(item_descr_width * 0.03)
        roi = [match.region[0] - delta_x, roi_y, item_descr_width + 2 * delta_x, search_height]

        sep_short = search(
            SHORT_SEPARATOR_REFS, img, 0.8, roi, use_grayscale=True, mode="first", do_multi_process=False
        )

        if sep_short.success:
            off_bottom_of_descr = ResManager().offsets.item_descr_off_bottom_edge
            roi_height = ResManager().pos.window_dimensions[1] - (2 * off_bottom_of_descr) - match.region[1]
            if (
                res_bottom := search(
                    ref=["item_bottom_edge"], inp_img=img, roi=roi, threshold=0.54, use_grayscale=True, mode="all"
                )
            ).success:
                # Internal tooltip separators can match the bottom-edge template more strongly than the actual edge.
                bottom_edge = max(res_bottom.matches, key=lambda candidate: candidate.center[1])
                detected_height = bottom_edge.center[1] - off_bottom_of_descr - match.region[1]
                if detected_height > 0:
                    roi_height = detected_height
            crop_roi = [
                match.region[0] + item_descr_pad,
                match.region[1] + item_descr_pad,
                item_descr_width - 2 * item_descr_pad,
                roi_height,
            ]
            crop_roi_tuple = (crop_roi[0], crop_roi[1], crop_roi[2], crop_roi[3])
            cropped_descr = crop(img, crop_roi_tuple)
            return True, rarity, cropped_descr, crop_roi_tuple

    return False, None, None, None
