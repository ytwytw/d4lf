from pathlib import Path

import cv2
import numpy as np
import pytest

from src.inventory_dump.layout import (
    INVENTORY_PAGES,
    _has_slot_frame,
    equipment_targets,
    find_tabs,
    scale_point,
    tab_selected,
)

DATA = Path(__file__).parent / "data"


def _read_band(name: str) -> np.ndarray:
    result = cv2.imread(str(DATA / name))
    assert result is not None
    return result


def _frame() -> np.ndarray:
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[125:211, 20:670] = _read_band("stash_tabs.png")
    image[669:720, 1230:1900] = _read_band("inventory_tabs.png")
    return image


@pytest.mark.parametrize("resolution", [(1920, 1080), (2560, 1440), (3840, 2160)])
def test_observed_stash_tabs_are_discovered_without_configured_count(resolution) -> None:
    image = cv2.resize(_frame(), resolution)
    tabs = find_tabs(image, stash=True)
    assert len(tabs) == 7
    assert [tab.name for tab in tabs] == [str(index) for index in range(1, 8)]
    assert [tab.name for tab in tabs if tab_selected(image, tab)] == ["2"]


def test_all_five_inventory_categories_are_located_and_selected_tab_verified() -> None:
    image = _frame()
    tabs = find_tabs(image)
    assert [tab.name for tab in tabs] == list(INVENTORY_PAGES)
    assert [tab.name for tab in tabs if tab_selected(image, tab)] == ["equipment"]


def test_missing_stash_tabs_are_not_invented_and_blank_frame_has_no_click_targets() -> None:
    image = _frame()
    image[125:211, 400:670] = 0
    assert len(find_tabs(image, stash=True)) == 4
    assert find_tabs(np.zeros_like(image), stash=True) == []
    assert find_tabs(np.zeros_like(image)) == []


def test_inventory_navigation_is_right_anchored_on_widescreen() -> None:
    image = np.zeros((1080, 2560, 3), dtype=np.uint8)
    image[669:720, 1870:2540] = _read_band("inventory_tabs.png")
    assert len(find_tabs(image)) == 5
    assert scale_point(image, 1860, 693, right=True) == (2500, 693)


def test_custom_or_unknown_stash_icon_retains_its_scope_and_page_number() -> None:
    image = _frame()
    image[158:193, 274:305] = 0
    tabs = find_tabs(image, stash=True)
    assert len(tabs) == 7
    assert tabs[2].name == "3"
    assert not tabs[2].icon_recognized
    assert tabs[3].name == "4"


@pytest.mark.parametrize("shape", [(2, 4), (2, 1, 4)])
def test_equipment_frame_detection_accepts_opencv_line_array_shapes(mocker, shape) -> None:
    lines = np.array([[10, 5, 10, 100], [70, 5, 70, 100]]).reshape(shape)
    mocker.patch("src.inventory_dump.layout.cv2.HoughLinesP", return_value=lines)
    assert _has_slot_frame(np.zeros((1080, 1920, 3), dtype=np.uint8), (1497, 122))


def test_equipment_frame_requires_edges_on_both_sides_of_the_hover_target(mocker) -> None:
    lines = np.array([[65, 5, 65, 100], [72, 5, 72, 100]])
    mocker.patch("src.inventory_dump.layout.cv2.HoughLinesP", return_value=lines)
    assert not _has_slot_frame(np.zeros((1080, 1920, 3), dtype=np.uint8), (1497, 122))


@pytest.mark.parametrize("resolution", [(1920, 1080), (2560, 1440), (3840, 2160)])
def test_live_equipment_panel_has_ten_slots_without_character_or_adjacent_weapon_false_positives(resolution) -> None:
    image = np.zeros((1440, 2560, 3), dtype=np.uint8)
    image[90:885, 1930:2545] = _read_band("equipment_panel.webp")
    targets = equipment_targets(cv2.resize(image, resolution))
    assert {name for name, _center in targets} == {
        "head",
        "chest",
        "gloves",
        "legs",
        "boots",
        "weapon_left",
        "amulet",
        "ring_upper",
        "ring_lower",
        "weapon_right",
    }
