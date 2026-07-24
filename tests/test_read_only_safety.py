import threading
from types import SimpleNamespace
from unittest.mock import call

import pytest
from pydantic import ValidationError

from src import loot_mover
from src.config.settings_models import AdvancedOptionsModel, CharModel, GeneralModel, ItemRefreshType, MoveItemsType
from src.scripts import common, handler, info_overlay, loot_filter_tts
from src.ui.inventory_base import ItemSlot


def _config(language: str) -> SimpleNamespace:
    return SimpleNamespace(
        advanced_options=AdvancedOptionsModel(vision_mode_only=False),
        char=CharModel(),
        general=GeneralModel(language=language),
    )


@pytest.fixture
def set_language(mocker):
    def _set_language(language: str) -> SimpleNamespace:
        config = _config(language)
        mocker.patch.object(common, "IniConfigLoader", return_value=config)
        mocker.patch.object(common, "is_window_foreground", return_value=True)
        return config

    return _set_language


@pytest.mark.parametrize(("language", "read_only"), [("enUS", False), ("zhCN", False)])
def test_language_policy_is_derived_from_language(language: str, read_only: bool) -> None:
    assert GeneralModel(language=language).read_only is read_only


def test_read_only_cannot_be_overridden() -> None:
    with pytest.raises(ValidationError):
        GeneralModel.model_validate({"language": "zhCN", "read_only": False})

    with pytest.raises(ValidationError, match="language not supported"):
        GeneralModel(language="frFR")


def test_diagnostic_capture_blocks_shared_keyboard_mouse_and_hover_outlets(mocker, set_language) -> None:
    set_language("zhCN")
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=True)
    hotkeys = mocker.patch.object(common, "hotkeys")
    mouse = mocker.patch.object(common, "Mouse")
    cam = mocker.patch.object(common, "Cam")
    sleep = mocker.patch.object(common.time, "sleep")
    inventory = mocker.Mock()
    occupied = [SimpleNamespace(is_fav=True, is_junk=False), SimpleNamespace(is_fav=False, is_junk=True)]

    common.mark_as_junk()
    common.mark_as_favorite()
    common.reset_item_status(occupied, inventory)
    common.drop_item_from_inventory()
    common.use_item_from_inventory()

    assert hotkeys.mock_calls == []
    assert mouse.mock_calls == []
    assert cam.mock_calls == []
    assert inventory.mock_calls == []
    sleep.assert_not_called()


@pytest.mark.parametrize("language", ["enUS", "zhCN"])
def test_supported_languages_share_input_behavior(mocker, set_language, language) -> None:
    set_language(language)
    hotkeys = mocker.patch.object(common, "hotkeys")
    mouse = mocker.patch.object(common, "Mouse")
    cam = mocker.patch.object(common, "Cam")
    mocker.patch.object(common.time, "sleep")

    common.mark_as_junk()
    hotkeys.send.assert_called_once_with("space")

    hotkeys.reset_mock()
    common.mark_as_favorite()
    assert hotkeys.send.call_args_list == [call("space"), call("space")]

    hotkeys.reset_mock()
    inventory = mocker.Mock()
    favorite = SimpleNamespace(is_fav=True, is_junk=False)
    junk = SimpleNamespace(is_fav=False, is_junk=True)
    cam.return_value.abs_window_to_monitor.return_value = (10, 20)
    common.reset_item_status([favorite, junk], inventory)
    assert inventory.hover_item_with_delay.call_args_list == [call(favorite), call(junk)]
    assert hotkeys.send.call_args_list == [call("space"), call("space"), call("space")]
    mouse.move.assert_called_once_with(10, 20)

    hotkeys.reset_mock()
    mouse.reset_mock()
    common.drop_item_from_inventory()
    hotkeys.press.assert_called_once_with("ctrl")
    hotkeys.release.assert_called_once_with("ctrl")
    mouse.click.assert_called_once_with("left")

    mouse.reset_mock()
    common.use_item_from_inventory()
    mouse.click.assert_called_once_with("right")


def test_delayed_input_sequences_recheck_the_policy(mocker) -> None:
    allowed = mocker.patch.object(common, "game_input_allowed", side_effect=[True, False])
    hotkeys = mocker.patch.object(common, "hotkeys")
    mouse = mocker.patch.object(common, "Mouse")
    mocker.patch.object(common.time, "sleep")

    common.mark_as_favorite()

    hotkeys.send.assert_called_once_with("space")

    allowed.side_effect = [True, True, False]
    hotkeys.reset_mock()
    inventory = mocker.Mock()
    junk = SimpleNamespace(is_fav=False, is_junk=True)
    common.reset_item_status([junk], inventory)

    inventory.hover_item_with_delay.assert_called_once_with(junk)
    hotkeys.send.assert_not_called()
    assert mouse.mock_calls == []

    allowed.side_effect = [True, False]
    hotkeys.reset_mock()
    mouse.reset_mock()

    common.drop_item_from_inventory()

    hotkeys.press.assert_called_once_with("ctrl")
    hotkeys.release.assert_called_once_with("ctrl")
    mouse.click.assert_not_called()


def test_game_input_is_blocked_when_diablo_is_not_foreground(mocker, set_language) -> None:
    set_language("zhCN")
    mocker.patch.object(common, "is_window_foreground", return_value=False)
    hotkeys = mocker.patch.object(common, "hotkeys")
    mouse = mocker.patch.object(common, "Mouse")

    common.mark_as_junk()
    common.mark_as_favorite()
    common.drop_item_from_inventory()
    common.use_item_from_inventory()

    assert hotkeys.mock_calls == []
    assert mouse.mock_calls == []


def test_diagnostic_capture_blocks_every_filter_input_action(mocker, set_language) -> None:
    set_language("zhCN")
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=True)
    inventory = mocker.Mock()
    input_actions = [
        mocker.patch.object(loot_filter_tts, "drop_item_from_inventory"),
        mocker.patch.object(loot_filter_tts, "mark_as_favorite"),
        mocker.patch.object(loot_filter_tts, "mark_as_junk"),
        mocker.patch.object(loot_filter_tts, "reset_item_status"),
        mocker.patch.object(loot_filter_tts, "use_item_from_inventory"),
    ]
    cam = mocker.patch.object(loot_filter_tts, "Cam")

    loot_filter_tts.check_items(
        inventory, ItemRefreshType.force_with_filter, stash_is_open=False, no_match_action="drop"
    )

    assert inventory.mock_calls == []
    assert cam.mock_calls == []
    for action in input_actions:
        action.assert_not_called()


def test_diagnostic_capture_blocks_transfer_hover_click_tab_and_pointer_outlets(mocker, set_language) -> None:
    set_language("zhCN")
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=True)
    char_inventory = mocker.patch.object(loot_mover, "CharInventory")
    stash = mocker.patch.object(loot_mover, "Stash")
    mouse = mocker.patch.object(loot_mover, "Mouse")
    cam = mocker.patch.object(loot_mover, "Cam")

    loot_mover.move_items_to_stash()
    loot_mover.move_items_to_inventory()

    char_inventory.assert_not_called()
    stash.assert_not_called()
    assert mouse.mock_calls == []
    assert cam.mock_calls == []

    inventory = mocker.Mock()
    slot = ItemSlot(bounding_box=(0, 0, 1, 1), center=(0, 0))
    result = loot_mover._move_items(inventory, [slot], 1, [MoveItemsType.unmarked])

    assert result == (0, [slot])
    assert inventory.mock_calls == []
    assert mouse.mock_calls == []


@pytest.mark.parametrize("language", ["enUS", "zhCN"])
def test_supported_languages_share_transfer_behavior(mocker, set_language, language) -> None:
    set_language(language)
    mouse = mocker.patch.object(loot_mover, "Mouse")
    inventory = mocker.Mock()
    slot = ItemSlot(bounding_box=(0, 0, 1, 1), center=(0, 0))

    result = loot_mover._move_items(inventory, [slot], 1, [MoveItemsType.unmarked])

    assert result == (1, [])
    inventory.hover_item.assert_called_once_with(slot)
    mouse.click.assert_called_once_with("right")


@pytest.mark.parametrize(("language", "interaction_hotkeys_enabled"), [("enUS", True), ("zhCN", True)])
def test_interaction_hotkeys_follow_language_policy(
    mocker, set_language, language, interaction_hotkeys_enabled
) -> None:
    config = set_language(language)
    script_handler = handler.ScriptHandler.__new__(handler.ScriptHandler)
    script_handler._config = config
    script_handler._hotkey_handles = []
    script_handler._register_hotkey = mocker.Mock()

    script_handler.setup_key_binds()

    registered_hotkeys = {registered.args[0] for registered in script_handler._register_hotkey.call_args_list}
    safe_hotkeys = {
        config.advanced_options.run_vision_mode,
        config.advanced_options.exit_key,
        config.advanced_options.toggle_paragon_overlay,
        config.advanced_options.info_overlay,
    }
    interaction_hotkeys = {
        config.char.inventory,
        config.advanced_options.run_filter,
        config.advanced_options.run_filter_drop,
        config.advanced_options.run_filter_force_refresh,
        config.advanced_options.force_refresh_only,
        config.advanced_options.move_to_inv,
        config.advanced_options.move_to_chest,
    }

    assert safe_hotkeys <= registered_hotkeys
    assert interaction_hotkeys_enabled is interaction_hotkeys.issubset(registered_hotkeys)
    assert script_handler._current_hotkey_signature[-1] == language


def test_language_change_refreshes_hotkeys_and_assets(mocker) -> None:
    script_handler = handler.ScriptHandler.__new__(handler.ScriptHandler)
    script_handler._runtime_config_lock = threading.RLock()
    script_handler._config = _config("zhCN")
    script_handler._refresh_hotkeys = mocker.Mock()
    script_handler._refresh_language_assets = mocker.Mock()
    script_handler._notify_manual_restart_required = mocker.Mock()
    script_handler.stop_active_game_input = mocker.Mock()

    script_handler._on_config_changed(frozenset({"general.language"}))

    script_handler._refresh_hotkeys.assert_called_once_with(script_handler._config)
    script_handler._refresh_language_assets.assert_called_once_with(script_handler._config)
    script_handler.stop_active_game_input.assert_called_once_with()


def test_stopping_active_game_input_waits_for_interaction_lock(mocker) -> None:
    class RecordingLock:
        entered = False
        exited = False

        def __enter__(self):
            self.entered = True

        def __exit__(self, _exc_type, _exc_value, _traceback):
            self.exited = True

    script_handler = handler.ScriptHandler.__new__(handler.ScriptHandler)
    script_handler._stop_active_game_input_locked = mocker.Mock()
    interaction_lock = RecordingLock()
    mocker.patch.object(handler, "LOCK", interaction_lock)

    script_handler.stop_active_game_input()

    assert interaction_lock.entered
    assert interaction_lock.exited
    script_handler._stop_active_game_input_locked.assert_called_once_with()


def test_experience_hover_rechecks_policy_before_each_mouse_move(mocker) -> None:
    allowed = mocker.patch.object(info_overlay, "game_input_allowed", side_effect=[True, False])
    mouse = mocker.patch.object(info_overlay, "Mouse")
    cam = mocker.patch.object(info_overlay, "Cam")
    mocker.patch.object(info_overlay.time, "sleep")
    cam.return_value.window_to_monitor.side_effect = [(10, 20), (30, 40)]

    info_overlay._hover_experience_balance({"exp_bar_pos": (1, 2, 3, 4)})

    mouse.move.assert_called_once_with(10, 20)
    assert allowed.call_count == 2


def test_experience_hover_stops_when_policy_changes_during_delay(mocker) -> None:
    tracker = info_overlay.InventoryExpTracker()
    tracker.last_hover_time = 0
    tracker.hover_active = False
    mocker.patch.object(info_overlay, "_OVERLAY_INSTANCE", object())
    mocker.patch.object(info_overlay, "_BUSY_CHECKER", return_value=False)
    mocker.patch.object(
        info_overlay,
        "load_info_settings",
        return_value={"capture_exp_stats": True, "exp_age_before_refresh": 5, "check_exp_on_inventory_open": True},
    )
    mocker.patch.object(
        info_overlay,
        "IniConfigLoader",
        return_value=SimpleNamespace(advanced_options=SimpleNamespace(vision_mode_only=False)),
    )
    mocker.patch.object(info_overlay, "SessionStats", return_value=SimpleNamespace(last_exp=None))
    mocker.patch.object(info_overlay.time, "time", return_value=10)
    mocker.patch.object(info_overlay.time, "sleep")
    mocker.patch.object(info_overlay, "game_input_allowed", side_effect=[True, False])
    hover = mocker.patch.object(info_overlay, "_hover_experience_balance")
    mouse = mocker.patch.object(info_overlay, "Mouse")

    thread = mocker.patch.object(info_overlay.threading, "Thread")
    thread.return_value.start.side_effect = lambda: thread.call_args.kwargs["target"]()

    tracker.on_inventory_open()

    hover.assert_not_called()
    assert mouse.mock_calls == []


def test_diagnostic_capture_blocks_handler_entry_points_and_direct_runner(mocker, set_language) -> None:
    set_language("zhCN")
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=True)
    script_handler = handler.ScriptHandler.__new__(handler.ScriptHandler)
    script_handler._start_or_stop_loot_interaction_thread = mocker.Mock()
    mocker.patch.object(handler.src.tts, "CONNECTED", True)

    script_handler.filter_items(no_match_action="drop")
    script_handler.move_items_to_inventory()
    script_handler.move_items_to_stash()

    script_handler._start_or_stop_loot_interaction_thread.assert_not_called()

    direct_handler = handler.ScriptHandler.__new__(handler.ScriptHandler)
    direct_handler.loot_interaction_thread = None
    thread = mocker.patch.object(handler.threading, "Thread")
    direct_handler._start_or_stop_loot_interaction_thread(mocker.Mock())
    thread.assert_not_called()

    wrapped_handler = handler.ScriptHandler.__new__(handler.ScriptHandler)
    wrapped_handler.loot_interaction_thread = object()
    wrapped_handler.vision_mode = mocker.Mock()
    interaction = mocker.Mock()
    wrapped_handler._wrapper_run_loot_interaction_method(interaction)
    interaction.assert_not_called()
    assert wrapped_handler.vision_mode.mock_calls == []
    assert wrapped_handler.loot_interaction_thread is None

    mouse = mocker.patch.object(handler, "Mouse")
    cam = mocker.patch.object(handler, "Cam")
    char_inventory = mocker.patch.object(handler, "CharInventory")
    stash = mocker.patch.object(handler, "Stash")
    check_items = mocker.patch.object(handler.src.scripts.loot_filter_tts, "check_items")

    handler.run_loot_filter(ItemRefreshType.force_with_filter, no_match_action="drop")

    assert mouse.mock_calls == []
    assert cam.mock_calls == []
    char_inventory.assert_not_called()
    stash.assert_not_called()
    check_items.assert_not_called()
