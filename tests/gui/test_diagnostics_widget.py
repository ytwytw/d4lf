import builtins
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.diagnostics.tts_capture import AppTtsCaptureController
from src.gui import diagnostics_widget
from src.gui.diagnostics_widget import DiagnosticsWidget, parse_game_build


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_parse_game_build_uses_the_untruncated_string_version() -> None:
    assert parse_game_build("3.1.0.72698") == "3.1.0.72698"
    assert parse_game_build("Product 3.1.0.72698 release") == "3.1.0.72698"
    assert parse_game_build("3, 1, 0, 72698") == "3.1.0.72698"
    assert parse_game_build("3.1") is None


def test_game_build_detection_reads_the_string_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_file_version_info(_executable: str, query: str):
        if query == r"\VarFileInfo\Translation":
            return [(0x0409, 0x04B0)]
        if query.endswith("ProductVersion"):
            return "3.1.0.72698"
        return ""

    monkeypatch.setattr(diagnostics_widget, "_get_file_version_info", get_file_version_info)

    assert diagnostics_widget.game_build_from_version_resource("Diablo IV.exe") == "3.1.0.72698"


def test_diagnostics_widget_saves_raw_capture_and_replay_report(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = app
    timestamps = iter([
        datetime(2026, 7, 10, 20, 30, 0, tzinfo=UTC),
        datetime(2026, 7, 10, 20, 30, 1, tzinfo=UTC),
        datetime(2026, 7, 10, 20, 30, 2, tzinfo=UTC),
    ])
    controller = AppTtsCaptureController(clock=lambda: next(timestamps), monotonic=lambda: 10.0)
    monkeypatch.setattr("src.gui.diagnostics_widget.detect_running_game_build", lambda _process_name: None)
    assets_root = Path(__file__).resolve().parents[2] / "assets" / "lang"
    lifecycle_events = []
    widget = DiagnosticsWidget(
        controller=controller,
        capture_dir=tmp_path,
        assets_root=assets_root,
        initial_locale="zhCN",
        on_capture_started=lambda: lifecycle_events.append("started"),
        on_capture_ended=lambda: lifecycle_events.append("ended"),
    )
    widget.build_input.setText("3.1.0.72698")

    widget.start_button.click()
    assert controller.record_payload("背包\0".encode())
    assert controller.record_payload(b"Mouse Button 4\0")
    widget.stop_button.click()

    assert widget.last_output_path is not None
    assert widget.last_output_path.exists()
    assert widget.last_report_path is not None
    assert widget.last_report_path.exists()
    report = json.loads(widget.last_report_path.read_text(encoding="utf-8"))
    assert report["record_count"] == 2
    assert widget.stop_button.isEnabled() is False
    assert widget.start_button.isEnabled() is True
    assert lifecycle_events == ["started", "ended"]
    widget.refresh_status()
    assert lifecycle_events == ["started", "ended"]
    widget.close()


def test_diagnostics_widget_preserves_raw_capture_when_replay_import_fails(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = app
    timestamps = iter([
        datetime(2026, 7, 10, 20, 40, 0, tzinfo=UTC),
        datetime(2026, 7, 10, 20, 40, 1, tzinfo=UTC),
        datetime(2026, 7, 10, 20, 40, 2, tzinfo=UTC),
    ])
    controller = AppTtsCaptureController(clock=lambda: next(timestamps), monotonic=lambda: 10.0)
    monkeypatch.setattr("src.gui.diagnostics_widget.detect_running_game_build", lambda _process_name: None)
    widget = DiagnosticsWidget(
        controller=controller,
        capture_dir=tmp_path,
        assets_root=Path(__file__).resolve().parents[2] / "assets" / "lang",
        initial_locale="zhCN",
    )
    widget.build_input.setText("3.1.0.72698")
    widget.start_button.click()
    assert controller.record_payload("背包\0".encode())

    original_import = builtins.__import__

    def fail_replay_import(name, *args, **kwargs):
        if name == "src.tools.tts_replay":
            msg = "simulated frozen replay import failure"
            raise ImportError(msg)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_replay_import)
    widget.stop_button.click()

    assert widget.last_output_path is not None
    assert widget.last_output_path.exists()
    assert widget.last_report_path is None
    assert widget._last_replay_error == "simulated frozen replay import failure"
    widget.close()


def test_diagnostics_widget_shutdown_finalizes_an_active_capture(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = app
    timestamps = iter([datetime(2026, 7, 10, 21, 0, 0, tzinfo=UTC), datetime(2026, 7, 10, 21, 0, 1, tzinfo=UTC)])
    controller = AppTtsCaptureController(clock=lambda: next(timestamps), monotonic=lambda: 10.0)
    monkeypatch.setattr("src.gui.diagnostics_widget.detect_running_game_build", lambda _process_name: None)
    widget = DiagnosticsWidget(
        controller=controller,
        capture_dir=tmp_path,
        assets_root=Path(__file__).resolve().parents[2] / "assets" / "lang",
        initial_locale="zhCN",
    )
    widget.build_input.setText("3.1.0.72698")
    widget.start_button.click()
    assert controller.record_payload("背包\0".encode())

    widget.shutdown()

    assert not controller.is_active
    assert widget.last_output_path is not None
    assert widget.last_output_path.exists()
    assert widget.last_report_path is not None
    assert widget.last_report_path.exists()
    widget.close()


def test_diagnostics_widget_finishes_lifecycle_after_async_capture_error(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = app
    fixed_time = datetime(2026, 7, 10, 22, 0, 0, tzinfo=UTC)
    controller = AppTtsCaptureController(clock=lambda: fixed_time, monotonic=lambda: 10.0)
    monkeypatch.setattr("src.gui.diagnostics_widget.detect_running_game_build", lambda _process_name: None)
    lifecycle_events = []
    widget = DiagnosticsWidget(
        controller=controller,
        capture_dir=tmp_path,
        assets_root=Path(__file__).resolve().parents[2] / "assets" / "lang",
        initial_locale="zhCN",
        on_capture_started=lambda: lifecycle_events.append("started"),
        on_capture_ended=lambda: lifecycle_events.append("ended"),
    )
    widget.build_input.setText("3.1.0.72698")
    widget.start_button.click()

    assert not controller.record_payload(b"\xff")
    widget.refresh_status()

    assert lifecycle_events == ["started", "ended"]
    widget.shutdown()
    assert lifecycle_events == ["started", "ended"]
    widget.close()
