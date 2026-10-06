from threading import Event

import numpy as np
import pytest

from src.automation import WindowSpec, character_inventory, stash_inventory
from src.inventory_dump.layout import TabTarget, scale_point
from src.inventory_dump.navigation import NavigationError, Navigator
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
