import math
from typing import TYPE_CHECKING

import cv2
import numpy as np

from src.config.data import COLORS
from src.config.ui import ResManager
from src.template_finder import TemplateMatch, search
from src.utils.image_operations import color_filter, crop

if TYPE_CHECKING:
    from collections.abc import Iterator


def find_seperators_long(img_item_descr: np.ndarray, sep_short_match: TemplateMatch) -> list[TemplateMatch] | None:
    refs = ["item_seperator_long_legendary", "item_seperator_long_mythic"]
    roi = [0, sep_short_match.center[1], img_item_descr.shape[1], img_item_descr.shape[0] - sep_short_match.center[1]]
    if not (
        sep_long := search(refs, img_item_descr, 0.80, roi, use_grayscale=True, mode="all", do_multi_process=False)
    ).success:
        return None
    matches_dict = {}
    for match in sep_long.matches:
        match_exists = False
        for center in matches_dict:
            if math.sqrt((center[0] - match.center[0]) ** 2 + (center[1] - match.center[1]) ** 2) <= 10:
                if match.score > matches_dict[center].score:
                    matches_dict[center] = match
                match_exists = True
                break
        if not match_exists:
            matches_dict[match.center] = match
    filtered_matches = list(matches_dict.values())
    return sorted(filtered_matches, key=lambda match: match.center[1])


def find_seperator_short(img_item_descr: np.ndarray) -> TemplateMatch | None:
    refs = ["item_seperator_short_rare", "item_seperator_short_legendary", "item_seperator_short_mythic"]
    roi = [
        0,
        int(ResManager().offsets.find_seperator_short_offset_top / 5),
        img_item_descr.shape[1],
        ResManager().offsets.find_seperator_short_offset_top,
    ]
    sep_short = search(refs, img_item_descr, 0.62, roi, use_grayscale=True, mode="all", do_multi_process=False)
    if not sep_short.success or not sep_short.matches:
        return None
    sorted_matches = sorted(sep_short.matches, key=lambda match: match.center[1])
    return sorted_matches[0]


def _filter_outliers(template_matches: list[TemplateMatch]) -> list[TemplateMatch]:
    # Extract center[0] values
    centers_x = [tm.center[0] for tm in template_matches]
    # Calculate the median
    if not centers_x:
        return []
    target_center_x = np.min(centers_x)
    # Filter out the outliers
    return [tm for tm in template_matches if abs(tm.center[0] - target_center_x) < 1.2 * tm.region[2]]


def _find_bullets(
    img_item_descr: np.ndarray, sep_short_match: TemplateMatch, template_list: list[str], threshold: float, mode: str
) -> list[TemplateMatch]:
    img_height, img_width = img_item_descr.shape[:2]
    tooltip_left = max(0, int(sep_short_match.region[0]))
    roi_width = min(ResManager().offsets.find_bullet_points_width, img_width - tooltip_left)
    if roi_width <= 0:
        return []
    roi_bullets = [tooltip_left, sep_short_match.center[1], roi_width, img_height]
    all_bullets = search(
        ref=template_list, inp_img=img_item_descr, threshold=threshold, roi=roi_bullets, use_grayscale=True, mode=mode
    )
    if not all_bullets.success:
        return []
    all_bullets.matches = _filter_outliers(all_bullets.matches)
    # go through the matches and filter out the ones that are too close to each other. only keep the one with higher probability
    matches_dict = {}
    for match in all_bullets.matches:
        match_exists = False
        for center in matches_dict:
            if math.sqrt((center[0] - match.center[0]) ** 2 + (center[1] - match.center[1]) ** 2) <= 10:
                if match.score > matches_dict[center].score:
                    matches_dict[center] = match
                match_exists = True
                break
        if not match_exists:
            matches_dict[match.center] = match
    filtered_matches = list(matches_dict.values())
    return sorted(filtered_matches, key=lambda match: match.center[1])


def _classify_colored_affix_bullet(hsv_patch: np.ndarray) -> str:
    bright_pixels = hsv_patch[hsv_patch[:, :, 2] >= 70]
    if not len(bright_pixels):
        return "affix_bullet_point_color"

    chromatic_pixels = bright_pixels[bright_pixels[:, 1] >= 45]
    if len(chromatic_pixels):
        hues = chromatic_pixels[:, 0]
        blue_fraction = np.mean((hues >= 95) & (hues <= 112))
        warm_fraction = np.mean((hues <= 20) | (hues >= 170))
        chromatic_fraction = len(chromatic_pixels) / len(bright_pixels)
        if blue_fraction >= 0.25:
            return "rerolled_bullet_point_color"
        if warm_fraction >= 0.60 and bright_pixels[:, 2].max() >= 180:
            return "greater_affix_bullet_point_color"
        if chromatic_fraction >= 0.45:
            return "tempered_affix_bullet_point_color"

    # Current Transfiguration glyphs are bright white. Keep them generic so the
    # TTS range still decides whether the affix itself is normal or greater.
    return "affix_bullet_point_color"


def _iter_active_rows(active_rows: np.ndarray) -> Iterator[tuple[int, int]]:
    start = None
    for index, is_active in enumerate(active_rows):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            yield start, index
            start = None
    if start is not None:
        yield start, len(active_rows)


def _find_colored_affix_bullets(
    img_item_descr: np.ndarray,
    sep_short_match: TemplateMatch,
    aspect_bullet: TemplateMatch | None,
    expected_count: int | None = None,
) -> list[TemplateMatch]:
    line_height = ResManager().offsets.item_descr_line_height
    image_height, image_width = img_item_descr.shape[:2]
    tooltip_left = max(0, int(sep_short_match.region[0]))
    if aspect_bullet is not None:
        left = max(tooltip_left, aspect_bullet.center[0] - round(line_height * 0.6))
        right = min(image_width, aspect_bullet.center[0] + round(line_height * 0.6))
    else:
        left = min(image_width, tooltip_left + round(line_height * 0.04))
        right = min(image_width, tooltip_left + round(line_height))
    top = min(image_height, sep_short_match.center[1] + round(line_height * 1.5))
    bottom = image_height
    if aspect_bullet is not None:
        bottom = max(top, aspect_bullet.center[1] - round(line_height * 0.45))
    if right <= left or bottom <= top:
        return []

    hsv_image = cv2.cvtColor(img_item_descr, cv2.COLOR_BGR2HSV)
    gray_gutter = cv2.cvtColor(img_item_descr[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    background = cv2.GaussianBlur(gray_gutter, (0, 0), sigmaX=max(0.8, line_height * 0.04))
    contrast = cv2.absdiff(gray_gutter, background)
    contrast_mask = (contrast >= 12).astype(np.uint8)
    foreground_mask = (gray_gutter.astype(np.int16) - background.astype(np.int16) >= 8).astype(np.uint8)

    row_signal = contrast_mask.sum(axis=1)
    active_rows = (row_signal >= max(2, round(line_height * 0.06))).astype(np.uint8) * 255
    close_height = max(3, round(line_height * 0.2))
    active_rows = cv2.morphologyEx(
        active_rows.reshape(-1, 1), cv2.MORPH_CLOSE, np.ones((close_height, 1), dtype=np.uint8)
    ).ravel()

    matches: list[TemplateMatch] = []
    min_row_height = max(3, round(line_height * 0.16))
    max_row_height = max(min_row_height, round(line_height * 1.1))
    min_row_signal = max(12, round(line_height))
    for row_start, row_end in _iter_active_rows(active_rows):
        if not (min_row_height <= row_end - row_start <= max_row_height):
            continue
        if row_signal[row_start:row_end].sum() < min_row_signal:
            continue

        row_mask = contrast_mask[row_start:row_end]
        _, signal_x = np.nonzero(row_mask)
        if not len(signal_x):
            continue
        x = left + int(signal_x.min())
        right_edge = left + int(signal_x.max()) + 1
        y = top + row_start
        bottom_edge = top + row_end

        patch = hsv_image[y:bottom_edge, x:right_edge].copy()
        patch_mask = foreground_mask[row_start:row_end, int(signal_x.min()) : int(signal_x.max()) + 1]
        patch[patch_mask == 0] = 0
        center_y = round(np.average(np.arange(y, bottom_edge), weights=row_signal[row_start:row_end].astype(float) + 1))
        region = [x, y, right_edge - x, bottom_edge - y]
        matches.append(
            TemplateMatch(
                center=(round((x + right_edge) / 2), center_y),
                center_monitor=(round((x + right_edge) / 2), center_y),
                name=_classify_colored_affix_bullet(patch),
                region=region,
                region_monitor=region.copy(),
                score=1.0,
            )
        )

    if aspect_bullet is None and expected_count is not None:
        return matches[: expected_count + 1]
    return matches


def _merge_affix_bullets(
    template_matches: list[TemplateMatch], color_matches: list[TemplateMatch], line_height: int
) -> list[TemplateMatch]:
    merged = list(template_matches)
    row_tolerance = max(4, round(line_height * 0.4))
    for color_match in color_matches:
        nearby_indexes = [
            index
            for index, template_match in enumerate(merged)
            if abs(template_match.center[1] - color_match.center[1]) <= row_tolerance
        ]
        if not nearby_indexes:
            merged.append(color_match)
            continue

        nearest_index = min(nearby_indexes, key=lambda index: abs(merged[index].center[1] - color_match.center[1]))
        template_match = merged[nearest_index]
        color_is_specific = not color_match.name.startswith("affix_bullet_point")
        template_is_specific = template_match.name.startswith(("greater_affix", "rerolled", "tempered_affix"))
        if color_is_specific or not template_is_specific:
            merged[nearest_index] = color_match
    return sorted(merged, key=lambda match: match.center[1])


def find_affix_bullets(
    img_item_descr: np.ndarray,
    sep_short_match: TemplateMatch,
    *,
    aspect_bullet: TemplateMatch | None = None,
    expected_count: int | None = None,
) -> list[TemplateMatch]:
    affix_icons = [f"affix_bullet_point_{x}" for x in range(1, 3)]
    rerolled_icons = [f"rerolled_bullet_point_{x}" for x in range(1, 3)]
    tempered_icons = [f"tempered_affix_bullet_point_{x}" for x in range(1, 7)]
    template_list = (
        [
            "greater_affix_bullet_point_1",
            "greater_affix_bullet_point_masterworked",
            "masterworking_affix_bullet",
            "masterworking_affix_bullet_2",
            "seal_set_bullet_point",
        ]
        + affix_icons
        + rerolled_icons
        + tempered_icons
    )

    all_templates = [f"{x}_medium" for x in template_list] + template_list
    search_threshold = 0.80
    if ResManager().resolution[1] <= 1200:
        all_templates += [
            "greater_affix_bullet_point_1080p_special",
            "greater_affix_bullet_point_masterworked_medium_1080p_special",
            "masterworking_affix_bullet_medium_1080p_special",
            "seal_set_bullet_point_1080p_special",
        ]
    template_matches = _find_bullets(
        img_item_descr=img_item_descr,
        sep_short_match=sep_short_match,
        template_list=all_templates,
        threshold=search_threshold,
        mode="all",
    )
    if aspect_bullet is not None:
        template_matches = [
            match
            for match in template_matches
            if match.center[1] < aspect_bullet.center[1] - ResManager().offsets.item_descr_line_height * 0.45
        ]

    color_matches = _find_colored_affix_bullets(
        img_item_descr, sep_short_match, aspect_bullet, expected_count=expected_count
    )
    return _merge_affix_bullets(template_matches, color_matches, ResManager().offsets.item_descr_line_height)


def find_aspect_bullet(img_item_descr: np.ndarray, sep_short_match: TemplateMatch) -> TemplateMatch | None:
    template_list = ["legendary_bullet_point", "unique_bullet_point", "mythic_bullet_point"]
    all_templates = [f"{x}_medium" for x in template_list] + template_list
    if ResManager().resolution[1] <= 1200:
        all_templates += ["mythic_bullet_point_1080p_special", "mythic_bullet_point_medium_1080p_special"]
    aspect_bullets = _find_bullets(
        img_item_descr=img_item_descr,
        sep_short_match=sep_short_match,
        template_list=all_templates,
        threshold=0.78,
        mode="all",
    )
    if aspect_bullets:
        return next(match for match in aspect_bullets if match.score == max(match.score for match in aspect_bullets))
    return None


def find_aspect_search_area(img_item_descr: np.ndarray, aspect_bullet: TemplateMatch) -> list[int]:
    line_height = ResManager().offsets.item_descr_line_height
    img_height, img_width = img_item_descr.shape[:2]
    offset_x = int(aspect_bullet.center[0] + int(line_height // 5))
    top = int(aspect_bullet.center[1] - int(line_height * 0.8))
    roi_aspect = [offset_x, top, int(img_width * 0.99) - offset_x, int(img_height * 0.95) - top]
    cropped_bottom = crop(img_item_descr, (roi_aspect[0], roi_aspect[1], roi_aspect[2], roi_aspect[3]))
    filtered, _ = color_filter(
        cropped_bottom, [COLORS.unique_gold.h_s_v_min, COLORS.unique_gold.h_s_v_max], calc_filtered_img=False
    )
    bounding_values = np.nonzero(filtered)
    if len(bounding_values[0]) > 0:
        roi_aspect[3] = bounding_values[0].max() + int(line_height * 0.4)
    return roi_aspect


def find_codex_upgrade_icon(img_item_descr: np.ndarray, aspect_bullet: TemplateMatch) -> bool:
    top_limit = img_item_descr.shape[0] // 2
    right_limit = img_item_descr.shape[1] // 2
    if aspect_bullet is not None:
        top_limit = aspect_bullet.center[1]
    cut_item_descr = img_item_descr[top_limit:, :right_limit]
    # TODO small font template fallback
    result = search(["codex_upgrade_icon_medium"], cut_item_descr, 0.78, use_grayscale=True, mode="first")
    if not result.success:
        result = search(["codex_upgrade_icon"], cut_item_descr, 0.78, use_grayscale=True, mode="first")
    return result.success
