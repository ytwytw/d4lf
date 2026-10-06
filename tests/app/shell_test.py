import logging
import threading
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QMainWindow

import src.app.shell as shell_module
from src.app.lifecycle import UnifiedWindowLifecycle
from src.app.shell import UnifiedMainWindow
from src.item.filter import ProfileLoadReport
from src.settings import SettingsLoadError


def test_shell_uses_application_window_lifecycle() -> None:
    assert issubclass(UnifiedMainWindow, UnifiedWindowLifecycle)


def test_profile_report_is_delivered_through_qt_signal() -> None:
    app = QApplication.instance() or QApplication([])
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    QMainWindow.__init__(window)  # ruff:ignore[unnecessary-dunder-call] - initialize a shell instance without its full UI
    received = []
    window.profile_load_report_signal.connect(received.append)

    window._queue_profile_load_report(ProfileLoadReport(skipped=("bad",), message="bad skipped"))
    app.processEvents()

    assert received[0].message == "bad skipped"
    window.deleteLater()


def test_settings_error_from_worker_is_delivered_on_gui_thread(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    QMainWindow.__init__(window)  # ruff:ignore[unnecessary-dunder-call] - initialize without full UI
    gui_thread = threading.get_ident()
    notification_threads = []
    monkeypatch.setattr(
        window,
        "tray_icon",
        SimpleNamespace(showMessage=lambda *_args: notification_threads.append(threading.get_ident())),
        raising=False,
    )
    window.settings_load_error_signal.connect(window._on_settings_load_error)
    error = SettingsLoadError(Path("params.ini"), ValueError("invalid"))

    worker = threading.Thread(target=window._queue_settings_load_error, args=(error,))
    worker.start()
    worker.join()
    app.processEvents()

    assert notification_threads == [gui_thread]
    window.deleteLater()


def test_profile_editor_inherits_main_window_maximized_state(monkeypatch) -> None:
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    monkeypatch.setattr(window, "isMaximized", lambda: True)
    calls = []
    monkeypatch.setattr(
        window,
        "_show_singleton_modal",
        lambda key, window_factory, **kwargs: calls.append((key, window_factory, kwargs)),
    )

    window.open_profile_editor("beta")

    assert calls == [("editor", shell_module.ProfileEditorWindow, {"profile_name": "beta", "force_maximized": True})]


def test_settings_window_inherits_main_window_maximized_state(monkeypatch) -> None:
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    monkeypatch.setattr(window, "isMaximized", lambda: True)
    monkeypatch.setattr(window, "apply_theme", lambda: None)
    calls = []
    monkeypatch.setattr(
        window,
        "_show_singleton_modal",
        lambda key, window_factory, **kwargs: calls.append((key, window_factory, kwargs)),
    )
    monkeypatch.setattr(shell_module, "set_accent_color", lambda _color: None)
    monkeypatch.setattr(shell_module, "get_filter_colors", lambda: SimpleNamespace(matched="#fff"))

    window.open_settings_dialog()

    assert calls == [
        ("config", shell_module.ConfigWindow, {"theme_changed_callback": window.apply_theme, "force_maximized": True})
    ]


def test_startup_log_replay_includes_cleanup_records_and_respects_level(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    QMainWindow.__init__(window)  # ruff:ignore[unnecessary-dunder-call] - initialize without full UI
    received = []
    startup_record = logging.makeLogRecord({"name": "d4lf-startup-test", "levelno": logging.WARNING})
    cleanup_record = logging.makeLogRecord({"name": "d4lf-startup-test", "levelno": logging.ERROR})
    quiet_record = logging.makeLogRecord({"name": "d4lf-startup-test", "levelno": logging.DEBUG})
    monkeypatch.setattr(shell_module, "consume_startup_log_records", lambda: [startup_record])
    window._config = SimpleNamespace(consume_deferred_cleanup_log_records=lambda: [cleanup_record, quiet_record])
    monkeypatch.setattr(
        window, "console_handler", SimpleNamespace(level=logging.WARNING, handle=received.append), raising=False
    )

    window._emit_startup_logs()

    assert received == [startup_record, cleanup_record]
    window.deleteLater()
    app.processEvents()
