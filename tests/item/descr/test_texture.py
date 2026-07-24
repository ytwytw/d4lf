import cv2
import numpy as np

from src.config.ui import ResManager
from src.item.descr.texture import _find_colored_affix_bullets
from src.template_finder import TemplateMatch


def _bgr(hue: int, saturation: int, value: int) -> tuple[int, int, int]:
    hsv_pixel = np.array([[[hue, saturation, value]]], dtype=np.uint8)
    blue, green, red = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0, 0]
    return int(blue), int(green), int(red)


def _match(center: tuple[int, int], *, region_x: int = 0) -> TemplateMatch:
    region = [region_x, center[1], 1, 1]
    return TemplateMatch(center=center, center_monitor=center, name="", region=region, region_monitor=region.copy())


def test_colored_affix_detection_finds_and_classifies_current_glyphs() -> None:
    previous_resolution = "x".join(str(value) for value in ResManager().resolution)
    ResManager().set_resolution("1920x1080")
    try:
        image = np.zeros((450, 360, 3), dtype=np.uint8)
        rows = [240, 267, 294, 321, 348]
        colors = [_bgr(0, 12, 128), _bgr(103, 142, 152), _bgr(8, 100, 230), _bgr(121, 130, 240), _bgr(0, 8, 220)]
        for center_y, color in zip(rows, colors, strict=True):
            cv2.rectangle(image, (10, center_y - 4), (17, center_y + 4), color, thickness=-1)
        # This is the aspect glyph and must not be returned as an affix.
        cv2.rectangle(image, (8, 371), (16, 379), _bgr(17, 230, 156), thickness=-1)

        matches = _find_colored_affix_bullets(image, _match((90, 186)), _match((12, 375)))

        assert [match.name for match in matches] == [
            "affix_bullet_point_color",
            "rerolled_bullet_point_color",
            "greater_affix_bullet_point_color",
            "tempered_affix_bullet_point_color",
            "affix_bullet_point_color",
        ]
        assert all(abs(match.center[1] - expected_y) <= 1 for match, expected_y in zip(matches, rows, strict=True))
    finally:
        ResManager().set_resolution(previous_resolution)


def test_colored_affix_detection_uses_local_contrast_on_bright_tooltip_background() -> None:
    previous_resolution = "x".join(str(value) for value in ResManager().resolution)
    ResManager().set_resolution("3840x2160")
    try:
        image = np.full((1100, 720, 3), _bgr(124, 80, 85), dtype=np.uint8)
        tooltip_left = 40
        rows = [385, 438, 492, 545, 600, 652]
        colors = [
            _bgr(8, 180, 245),
            _bgr(103, 190, 220),
            _bgr(121, 150, 235),
            _bgr(8, 180, 245),
            _bgr(0, 8, 230),
            _bgr(8, 180, 245),
        ]
        for center_y, color in zip(rows, colors, strict=True):
            cv2.rectangle(
                image, (tooltip_left + 10, center_y - 8), (tooltip_left + 30, center_y + 8), color, thickness=-1
            )

        # No aspect template is available. The expected count must keep the aspect
        # and large inherent glyphs below the affix rows from displacing affixes.
        cv2.rectangle(image, (tooltip_left + 8, 697), (tooltip_left + 32, 713), _bgr(17, 230, 190), thickness=-1)
        cv2.rectangle(image, (tooltip_left + 4, 920), (tooltip_left + 45, 970), _bgr(0, 5, 235), thickness=-1)

        matches = _find_colored_affix_bullets(
            image,
            _match((176 + tooltip_left, 281), region_x=tooltip_left),
            aspect_bullet=None,
            expected_count=len(rows),
        )

        assert len(matches) == len(rows) + 1
        assert all(abs(match.center[1] - expected_y) <= 1 for match, expected_y in zip(matches, rows, strict=False))
        assert [match.name for match in matches[: len(rows)]] == [
            "greater_affix_bullet_point_color",
            "rerolled_bullet_point_color",
            "tempered_affix_bullet_point_color",
            "greater_affix_bullet_point_color",
            "affix_bullet_point_color",
            "greater_affix_bullet_point_color",
        ]
        assert abs(matches[-1].center[1] - 705) <= 1
    finally:
        ResManager().set_resolution(previous_resolution)
