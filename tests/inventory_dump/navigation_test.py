from threading import Event

import numpy as np
import pytest

from src.automation import ItemSlot, WindowSpec, character_inventory, stash_inventory
from src.inventory_dump.layout import TabTarget, scale_point
from src.inventory_dump.navigation import (
    ICON_SETTLE_CAPTURES,
    ICON_SETTLE_MIN,
    ICON_SETTLE_POLL,
    NavigationError,
    Navigator,
)
from src.inventory_dump.reader import ScanCancelledError
from src.settings import get_ui_coordinates


def test_cancelled_navigation_never_sends_more_game_input(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    navigator.cancel = Event()
    navigator.cancel.set()
    move = mocker.patch("src.inventory_dump.navigation.move_pointer_direct")
    focus = mocker.patch("src.inventory_dump.navigation.move_window_to_foreground")
    with pytest.raises(ScanCancelledError):
        navigator.prepare()
    navigator.restore()
    with pytest.raises(ScanCancelledError):
        navigator.hover((10, 20))
    move.assert_not_called()
    focus.assert_not_called()


def test_focus_loss_stops_input_and_restoration(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    navigator.cancel = Event()
    navigator.window = WindowSpec("Diablo IV.exe")
    mocker.patch("src.inventory_dump.navigation.game_input_blocked", return_value=False)
    mocker.patch("src.inventory_dump.navigation.is_window_foreground", return_value=False)
    move = mocker.patch("src.inventory_dump.navigation.move_pointer_direct")
    navigator.restore()
    with pytest.raises(NavigationError, match="lost focus"):
        navigator.hover((10, 20))
    move.assert_not_called()


def test_inventory_open_wait_observes_cancellation_without_more_input(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    navigator.cancel = Event()
    navigator.window = WindowSpec("Diablo IV.exe")
    navigator.inventory = mocker.Mock()
    navigator.inventory.is_open.return_value = False
    mocker.patch.object(navigator, "neutral")
    mocker.patch("src.inventory_dump.navigation.capture", return_value=np.zeros((1080, 1920, 3), dtype=np.uint8))
    mocker.patch("src.inventory_dump.navigation.find_tabs", return_value=[])
    mocker.patch("src.inventory_dump.navigation.game_input_blocked", return_value=False)
    mocker.patch("src.inventory_dump.navigation.is_window_foreground", return_value=True)
    mocker.patch("src.inventory_dump.navigation.is_connected", return_value=True)
    send = mocker.patch("src.inventory_dump.navigation.send_hotkey", side_effect=lambda _: navigator.cancel.set())
    with pytest.raises(ScanCancelledError):
        navigator.inventory_tabs()
    send.assert_called_once()
    navigator.inventory.open.assert_not_called()


def test_stash_tabs_use_visible_controls_without_language_dependent_title_template(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    navigator.stash = mocker.Mock()
    navigator.stash.is_open.return_value = False
    mocker.patch.object(navigator, "check")
    mocker.patch.object(navigator, "neutral")
    mocker.patch.object(navigator, "wait")
    mocker.patch("src.inventory_dump.navigation.capture")
    tabs = [TabTarget("1", (342, 350), 0.9)]
    mocker.patch("src.inventory_dump.navigation.find_tabs", return_value=tabs)
    assert navigator.stash_tabs() == tabs
    navigator.stash.is_open.assert_not_called()


@pytest.mark.parametrize("resolution", [(1920, 1080), (2560, 1440), (3840, 2160)])
def test_grid_and_hover_use_physical_capture_pixels_without_second_scaling(mocker, resolution) -> None:
    coordinates = get_ui_coordinates()
    original = coordinates.resolution
    width, height = resolution
    coordinates.set_resolution(f"{width}x{height}")
    try:
        navigator = Navigator.__new__(Navigator)
        navigator.inventory = character_inventory()
        navigator.stash = stash_inventory()
        image = np.zeros((height, width, 3), dtype=np.uint8)
        mocker.patch.object(navigator, "check")
        mocker.patch.object(navigator, "wait")
        mocker.patch("src.inventory_dump.navigation.capture", return_value=image)
        # Desktop/window origin is an offset in physical pixels, never a DPI scale.
        origin = np.array([150, 70])
        convert = mocker.patch(
            "src.inventory_dump.navigation.window_to_monitor", side_effect=lambda p: np.array(p) + origin
        )
        move = mocker.patch("src.inventory_dump.navigation.move_pointer_direct")
        for stash, expected_count, reference in ((False, 33, (1295.5, 762.5)), (True, 50, (76.5, 317.5))):
            targets = navigator.grid_targets("1", stash=stash)
            assert len(targets) == expected_count
            expected = scale_point(image, *reference, right=not stash)
            assert np.allclose(targets[0].location.center, expected, atol=1)
            navigator.hover(targets[0].location.center)
            convert.assert_called_with(targets[0].location.center)
            move.assert_called_with(*(np.array(targets[0].location.center) + origin))
    finally:
        coordinates.set_resolution("x".join(str(value) for value in original))


def test_select_tab_dismisses_equipment_tooltip_before_visibility_detection(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    events = []
    target = TabTarget("talisman", (2275, 926), 0.9)
    image = np.zeros((1440, 2560, 3), dtype=np.uint8)
    mocker.patch.object(navigator, "check")
    mocker.patch.object(navigator, "neutral", side_effect=lambda: events.append("neutral"))
    mocker.patch.object(navigator, "wait", side_effect=lambda _: events.append("wait"))
    mocker.patch("src.inventory_dump.navigation.capture", side_effect=lambda **_: events.append("capture") or image)
    mocker.patch("src.inventory_dump.navigation.find_tabs", return_value=[target])
    mocker.patch("src.inventory_dump.navigation.tab_selected", return_value=True)
    click = mocker.patch("src.inventory_dump.navigation.click_pointer")
    navigator.select_tab(target)
    assert events[:3] == ["neutral", "wait", "capture"]
    click.assert_not_called()


def test_equipment_detection_dismisses_the_last_backpack_tooltip(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    events = []
    mocker.patch.object(navigator, "check")
    mocker.patch.object(navigator, "neutral", side_effect=lambda: events.append("neutral"))
    mocker.patch.object(navigator, "wait", side_effect=lambda _: events.append("wait"))
    mocker.patch("src.inventory_dump.navigation.capture", side_effect=lambda **_: events.append("capture"))
    mocker.patch("src.inventory_dump.navigation.equipment_targets", return_value=[])
    assert navigator.equipped_targets() == []
    assert events == ["neutral", "wait", "capture"]


BOXES = [(0, 0, 10, 10), (10, 0, 10, 10)]


def _frame(first_slot_level: int) -> np.ndarray:
    image = np.full((20, 20, 3), 5, dtype=np.uint8)
    image[0:10, 0:10] = first_slot_level
    return image


def _settling_navigator(mocker, frames: list[np.ndarray]):
    navigator = Navigator.__new__(Navigator)
    navigator.cancel = Event()
    waits: list[float] = []
    mocker.patch.object(navigator, "check")
    mocker.patch.object(navigator, "wait", side_effect=waits.append)
    capture = mocker.patch("src.inventory_dump.navigation.capture", side_effect=frames)

    def slots(image):
        occupied, empty = [], []
        for x, y, w, h in BOXES:
            slot = ItemSlot((x, y, w, h), (x + w // 2, y + h // 2))
            (occupied if image[y : y + h, x : x + w].mean() > 37 else empty).append(slot)
        return occupied, empty

    navigator.inventory = mocker.Mock()
    navigator.inventory.get_item_slots.side_effect = slots
    return navigator, waits, capture


def test_occupancy_is_classified_after_fading_icons_stop_changing(mocker) -> None:
    # The first capture after a tab switch shows a fading icon below the occupancy threshold.
    navigator, waits, capture = _settling_navigator(mocker, [_frame(level) for level in (20, 45, 80, 81)])
    targets = navigator.grid_targets("consumables")
    assert capture.call_count == 4
    assert waits == [ICON_SETTLE_MIN, ICON_SETTLE_POLL, ICON_SETTLE_POLL, ICON_SETTLE_POLL]
    assert [target.occupied for target in targets] == [True, False]
    assert targets[0].occupancy == {
        "source": "slot_screenshot_brightness",
        "verification": "unverified",
        "value": True,
        "icons_settled": True,
    }


def test_animated_grid_is_bounded_and_reported_as_unsettled(mocker) -> None:
    frames = [_frame(20 if index % 2 else 80) for index in range(ICON_SETTLE_CAPTURES)]
    navigator, waits, capture = _settling_navigator(mocker, frames)
    targets = navigator.grid_targets("keys")
    assert capture.call_count == ICON_SETTLE_CAPTURES
    assert sum(waits) == pytest.approx(ICON_SETTLE_MIN + (ICON_SETTLE_CAPTURES - 1) * ICON_SETTLE_POLL)
    assert all(target.occupancy is not None and target.occupancy["icons_settled"] is False for target in targets)
    # Dark pixels of a page that never settled are not proof of emptiness: the reader treats them as unknown.
    assert [target.occupied for target in targets] == [None, None]


def test_cancel_during_icon_settling_sends_no_capture_or_input(mocker) -> None:
    navigator = Navigator.__new__(Navigator)
    navigator.cancel = Event()
    navigator.cancel.set()
    navigator.inventory = mocker.Mock()
    mocker.patch.object(navigator, "check")
    capture = mocker.patch("src.inventory_dump.navigation.capture")
    with pytest.raises(ScanCancelledError):
        navigator.grid_targets("equipment")
    capture.assert_not_called()
