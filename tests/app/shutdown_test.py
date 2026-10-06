import json
import time
from threading import Event, RLock
from types import SimpleNamespace

import pytest

from src.app import dump_runtime, shutdown
from src.app.handler import ScriptHandler
from src.inventory_dump import ExportFormat
from src.inventory_dump.exporting import SnapshotWriter
from src.inventory_dump.layout import TabTarget
from src.inventory_dump.models import Location, ScanDocument
from src.inventory_dump.navigation import ScanTarget
from src.inventory_dump.reader import ScanCancelledError
from src.inventory_dump.scanner import Scanner
from tests.app.dump_runtime_test import _handler


def test_script_shutdown_disables_callbacks_before_stopping_overlays(monkeypatch, mocker) -> None:
    handler = object.__new__(ScriptHandler)
    handler._init_inventory_dump()
    calls = []
    handler._runtime_config_lock = RLock()
    monkeypatch.setattr(
        handler,
        "_config",
        SimpleNamespace(unregister_change_listener=lambda _: calls.append("unregister")),
        raising=False,
    )
    monkeypatch.setattr(handler, "_clear_key_binds", lambda: calls.append("hotkeys"))
    monkeypatch.setattr(handler, "vision_mode", SimpleNamespace(stop=lambda: calls.append("vision")), raising=False)
    handler.loot_interaction_thread = mocker.Mock()
    handler.loot_interaction_thread.is_alive.return_value = False
    handler.paragon_overlay_thread = None
    monkeypatch.setattr(shutdown, "begin_shutdown", lambda: calls.append("input gate"))
    monkeypatch.setattr(shutdown, "request_close_paragon", lambda: calls.append("paragon"))
    monkeypatch.setattr(shutdown, "request_close", lambda: calls.append("info"))

    shutdown.shutdown_scripts(handler)

    assert handler._shutting_down
    assert calls == ["input gate", "unregister", "hotkeys", "vision", "paragon", "info"]
    handler.loot_interaction_thread.join.assert_called_once_with(timeout=2)


def test_shutdown_does_not_restart_vision_mode(mocker) -> None:
    handler = object.__new__(ScriptHandler)
    handler._shutting_down = True
    handler.vision_mode = mocker.Mock()

    handler.run_vision_mode()

    handler.vision_mode.start.assert_not_called()


@pytest.fixture
def exit_state(monkeypatch):
    gate = []
    monkeypatch.setattr(shutdown, "_EXIT_REQUESTED", Event())
    monkeypatch.setattr(shutdown, "begin_shutdown", lambda: gate.append("input blocked"))
    return gate


def _start_dump(handler, mocker, tmp_path, *, honour_cancel: bool, release: Event):
    path = tmp_path / "inventory.json"
    reading = Event()

    def scan(*, output_format, cancel, on_progress):
        navigator = mocker.Mock()
        navigator.stash_tabs.return_value = [TabTarget("1", (1, 1), 1)]
        navigator.grid_targets.return_value = [ScanTarget(Location("stash", "1", "r01c01", (1, 1), 1, 1), True)]
        reader = mocker.Mock()

        def read(*_args, **_kwargs):
            reading.set()
            if honour_cancel:
                cancel.wait(5)
                raise ScanCancelledError
            release.wait(10)

        reader.read.side_effect = read
        return Scanner(navigator, reader, SnapshotWriter(path, output_format), on_progress).run(
            ScanDocument("zhCN", "t")
        )

    mocker.patch.object(dump_runtime, "scan_inventory", side_effect=scan)
    handler.start_inventory_dump(ExportFormat.JSON, lambda _: None, lambda _: None, lambda _: None)
    assert reading.wait(2)
    return path


def test_exit_without_an_export_stops_immediately(mocker, exit_state) -> None:
    handler = _handler(mocker)
    exits = []
    shutdown.request_exit(handler, exit_process=lambda: exits.append("exit"))
    assert exits == ["exit"]
    assert exit_state == []


def test_exit_during_export_blocks_input_saves_cancelled_snapshot_then_exits(mocker, tmp_path, exit_state) -> None:
    handler = _handler(mocker)
    handler.vision_mode.running.return_value = True
    path = _start_dump(handler, mocker, tmp_path, honour_cancel=True, release=Event())
    exited = Event()
    running_at_exit = []

    def exit_process() -> None:
        running_at_exit.append(handler.inventory_dump_running)
        exited.set()

    shutdown.request_exit(handler, timeout=3, exit_process=exit_process)
    assert exit_state == ["input blocked"]
    assert exited.wait(3)
    assert running_at_exit == [False]
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "cancelled"
    assert payload["finished_at"] is not None
    assert [item["status"] for item in payload["items"]] == ["interrupted"]
    handler.vision_mode.start.assert_not_called()


def test_hung_export_cannot_delay_exit_beyond_the_bound_and_second_press_is_immediate(
    mocker, tmp_path, exit_state
) -> None:
    handler = _handler(mocker)
    release = Event()
    _start_dump(handler, mocker, tmp_path, honour_cancel=False, release=release)
    exits = []
    try:
        started = time.monotonic()
        shutdown.request_exit(handler, timeout=0.3, exit_process=lambda: exits.append(time.monotonic() - started))
        shutdown.request_exit(handler, timeout=0.3, exit_process=lambda: exits.append("second press"))
        assert exits == ["second press"]
        deadline = time.monotonic() + 3
        while len(exits) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert len(exits) == 2
        assert 0.25 <= exits[1] < 2
    finally:
        release.set()
        handler.wait_for_inventory_dump(5)
