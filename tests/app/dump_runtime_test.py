from threading import Event
from types import SimpleNamespace

import pytest

from src.app import dump_runtime
from src.app.handler import ScriptHandler
from src.inventory_dump import ExportFormat, ScanResult
from src.settings import get_settings


def _handler(mocker):
    handler = object.__new__(ScriptHandler)
    handler._init_inventory_dump()
    handler._shutting_down = False
    handler._config = get_settings()
    mocker.patch.object(handler._config.advanced_options, "vision_mode_only", False)
    handler.loot_interaction_thread = None
    handler.paragon_overlay_thread = None
    handler.vision_mode = mocker.Mock()
    handler.vision_mode.running.return_value = False
    handler._win_spec = mocker.Mock()
    mocker.patch.object(dump_runtime, "move_window_to_foreground")
    mocker.patch.object(dump_runtime, "is_open", return_value=False)
    mocker.patch.object(dump_runtime, "APP_TTS_CAPTURE", SimpleNamespace(is_active=False))
    return handler


def test_dump_owns_input_until_cancelled_and_finishes_result(mocker, tmp_path):
    handler = _handler(mocker)
    started = Event()
    finished = Event()
    result = ScanResult(tmp_path / "partial.json", "cancelled", 2, 0, ())
    received = []

    def scan(*, output_format, cancel, on_progress):
        assert output_format == ExportFormat.JSON
        started.set()
        assert cancel.wait(3)
        return result

    mocker.patch.object(dump_runtime, "scan_inventory", side_effect=scan)
    handler.start_inventory_dump(
        ExportFormat.JSON, lambda _: None, lambda value: (received.append(value), finished.set()), pytest.fail
    )
    assert started.wait(2)
    assert handler.inventory_dump_running
    action = mocker.Mock()
    handler._start_or_stop_loot_interaction_thread(action)
    handler.run_vision_mode()
    action.assert_not_called()
    handler.vision_mode.start.assert_not_called()
    handler.cancel_inventory_dump()
    handler.wait_for_inventory_dump()
    assert finished.wait(2)
    assert not handler.inventory_dump_running
    assert received == [result]


def test_dump_rejects_active_filter_without_stopping_it(mocker):
    handler = _handler(mocker)
    handler.loot_interaction_thread = mocker.Mock()
    scan = mocker.patch.object(dump_runtime, "scan_inventory")
    with pytest.raises(RuntimeError, match="另一项"):
        handler.start_inventory_dump(ExportFormat.JSON, lambda _: None, lambda _: None, lambda _: None)
    scan.assert_not_called()
    handler.loot_interaction_thread.join.assert_not_called()


def test_dump_failure_releases_busy_and_restores_previous_vision(mocker):
    handler = _handler(mocker)
    handler.vision_mode.running.side_effect = [True, False]
    mocker.patch.object(dump_runtime, "scan_inventory", side_effect=OSError("disk unavailable"))
    finished = Event()
    errors = []
    handler.start_inventory_dump(
        ExportFormat.JSON, lambda _: None, pytest.fail, lambda error: (errors.append(error), finished.set())
    )
    assert finished.wait(2)
    assert not handler.inventory_dump_running
    handler.vision_mode.stop.assert_called_once()
    handler.vision_mode.start.assert_called_once()
    assert errors == ["disk unavailable"]
