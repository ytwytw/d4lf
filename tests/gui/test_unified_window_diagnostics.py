from types import SimpleNamespace
from typing import cast

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from src.gui import unified_window
from src.gui.unified_window import UnifiedMainWindow


class _VisionMode:
    def __init__(self, running: bool) -> None:
        self.is_running = running
        self.start_calls = 0
        self.stop_calls = 0

    def running(self) -> bool:
        return self.is_running

    def start(self) -> None:
        self.start_calls += 1
        self.is_running = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.is_running = False


def _window_with_vision(vision_mode: _VisionMode):
    handler = SimpleNamespace(vision_mode=vision_mode, stop_active_game_input=lambda: None)
    return SimpleNamespace(
        worker=SimpleNamespace(script_handler=handler), _diagnostic_vision_state=None, _closing=False
    )


def test_diagnostic_capture_starts_vision_and_restores_stopped_state() -> None:
    vision_mode = _VisionMode(running=False)
    window = _window_with_vision(vision_mode)

    UnifiedMainWindow._enable_vision_for_diagnostic_capture(window)
    assert vision_mode.running()
    assert vision_mode.start_calls == 1

    UnifiedMainWindow._restore_vision_after_diagnostic_capture(window)
    assert not vision_mode.running()
    assert vision_mode.stop_calls == 1


def test_diagnostic_capture_keeps_running_vision_and_repairs_external_stop() -> None:
    vision_mode = _VisionMode(running=True)
    window = _window_with_vision(vision_mode)

    UnifiedMainWindow._enable_vision_for_diagnostic_capture(window)
    assert vision_mode.start_calls == 0
    vision_mode.stop()

    UnifiedMainWindow._restore_vision_after_diagnostic_capture(window)
    assert vision_mode.running()
    assert vision_mode.start_calls == 1


def test_diagnostic_capture_stops_active_game_input(mocker) -> None:
    vision_mode = _VisionMode(running=False)
    window = _window_with_vision(vision_mode)
    window.worker.script_handler.stop_active_game_input = mocker.Mock()

    UnifiedMainWindow._enable_vision_for_diagnostic_capture(window)

    window.worker.script_handler.stop_active_game_input.assert_called_once_with()


def test_diagnostics_setting_change_requests_live_tab_update(mocker) -> None:
    signal = SimpleNamespace(emit=mocker.Mock())
    window = cast(
        "UnifiedMainWindow",
        SimpleNamespace(
            _config=SimpleNamespace(general=SimpleNamespace(show_diagnostics_tab=True)),
            diagnostics_page_change_requested=signal,
        ),
    )

    UnifiedMainWindow._on_config_changed_diagnostics_page(window, frozenset({"general.show_diagnostics_tab"}))

    signal.emit.assert_called_once_with(True)


def test_diagnostics_tab_is_created_and_removed_on_demand(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    created_tabs = []

    class DiagnosticsStub(QWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__()
            self.shutdown_calls = 0
            created_tabs.append(self)

        def shutdown(self) -> None:
            self.shutdown_calls += 1

    monkeypatch.setattr(unified_window, "DiagnosticsWidget", DiagnosticsStub)
    activity_tab = QWidget()
    console_tab = QWidget()
    tabs = QTabWidget()
    tabs.addTab(activity_tab, "Dashboard")
    tabs.addTab(console_tab, "Full Logs")
    window = cast(
        "UnifiedMainWindow",
        SimpleNamespace(
            activity_tab=activity_tab,
            console_output=console_tab,
            diagnostics_tab=None,
            tabs=tabs,
            _enable_vision_for_diagnostic_capture=lambda: None,
            _restore_vision_after_diagnostic_capture=lambda: None,
        ),
    )

    UnifiedMainWindow._show_diagnostics_tab(window)

    assert len(created_tabs) == 1
    assert window.diagnostics_tab is created_tabs[0]
    assert tabs.count() == 3
    assert tabs.tabText(2) == "Diagnostics"

    tabs.setCurrentWidget(window.diagnostics_tab)
    UnifiedMainWindow._hide_diagnostics_tab(window)

    assert created_tabs[0].shutdown_calls == 1
    assert window.diagnostics_tab is None
    assert tabs.count() == 2
    assert tabs.currentWidget() is activity_tab
    app.processEvents()
