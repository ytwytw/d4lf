import logging
import sys
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import src.app.backend as backend_module
from src.app.backend import BackendWorker

pytestmark = pytest.mark.usefixtures("offline_cleanup")


@pytest.fixture
def offline_cleanup(monkeypatch) -> None:
    monkeypatch.setattr(backend_module, "begin_shutdown", lambda: None)
    monkeypatch.setattr(backend_module, "shutdown_ui_thread", lambda: True)
    monkeypatch.setattr(backend_module, "stop_detecting_window", lambda: None, raising=False)


def test_backend_worker_finishes_in_gui_only_mode(monkeypatch, caplog) -> None:
    monkeypatch.setattr("src.app.backend.sys.platform", "linux")
    worker = BackendWorker()
    finished = []
    worker.finished.connect(lambda: finished.append(True))

    with caplog.at_level(logging.INFO):
        worker.run()

    assert finished == [True]
    assert "GUI-only mode" in caplog.text


@pytest.mark.skipif(sys.platform != "win32", reason="The game backend runtime is Windows-only.")
def test_backend_starts_tts_listener_before_waiting_for_game_window(monkeypatch) -> None:
    calls = []

    class Filter:
        def load_files(self) -> None:
            calls.append("load_files")

    class Overlay:
        def run(self, _stop_event) -> None:
            calls.append("overlay")

    perception = SimpleNamespace(start_connection=lambda: calls.append("tts"))
    monkeypatch.setattr(backend_module.sys, "platform", "win32")
    monkeypatch.setattr(backend_module, "Filter", Filter)
    monkeypatch.setattr(backend_module, "_perception", perception)
    monkeypatch.setattr(backend_module, "Overlay", Overlay)
    monkeypatch.setattr(backend_module, "start_detecting_window", lambda _spec: calls.append("detect_window"))
    monkeypatch.setattr(backend_module, "game_window_ready", lambda: True)
    monkeypatch.setattr(
        backend_module,
        "ScriptHandler",
        lambda: SimpleNamespace(shutdown=lambda: calls.append("shutdown"), cancel_inventory_dump=lambda: None),
    )
    monkeypatch.setattr(backend_module, "check_for_proper_tts_configuration", lambda: calls.append("diagnostics"))
    monkeypatch.setattr(
        backend_module,
        "get_settings",
        lambda: SimpleNamespace(advanced_options=SimpleNamespace(process_name="Diablo IV.exe")),
    )
    BackendWorker().run()

    assert calls.index("tts") < calls.index("load_files")
    assert calls[-2:] == ["overlay", "shutdown"]


@pytest.mark.skipif(sys.platform != "win32", reason="The game backend runtime is Windows-only.")
def test_backend_stop_cancels_wait_for_missing_game(monkeypatch) -> None:
    waiting = Event()
    calls = []
    monkeypatch.setattr(backend_module, "_perception", SimpleNamespace(start_connection=lambda: None))
    monkeypatch.setattr(backend_module, "Filter", lambda: SimpleNamespace(load_files=lambda: None))
    monkeypatch.setattr(backend_module, "start_detecting_window", lambda _: None)
    monkeypatch.setattr(backend_module, "game_window_ready", lambda: waiting.set() or False)
    monkeypatch.setattr(backend_module, "ScriptHandler", lambda: calls.append("unexpected handler"))
    worker = BackendWorker()
    thread = Thread(target=worker.run, daemon=True)
    thread.start()
    assert waiting.wait(1)

    worker.request_stop()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert calls == []


@pytest.mark.skipif(sys.platform != "win32", reason="The game backend runtime is Windows-only.")
def test_backend_failure_still_cleans_up_and_finishes(monkeypatch, caplog) -> None:
    worker = BackendWorker()
    calls = []

    def fail() -> None:
        message = "startup failed"
        raise RuntimeError(message)

    monkeypatch.setattr(worker, "_run_windows", fail)
    monkeypatch.setattr(worker, "_stop_scripts", lambda: calls.append("scripts"))
    monkeypatch.setattr(backend_module, "stop_detecting_window", lambda: calls.append("detection"))
    monkeypatch.setattr(backend_module, "shutdown_ui_thread", lambda: calls.append("tk"))
    worker.finished.connect(lambda: calls.append("finished"))

    worker.run()

    assert calls == ["scripts", "detection", "tk", "finished"]
    assert "Game backend failed" in caplog.text
