import os
from types import SimpleNamespace
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from src.diagnostics.tts_capture import AppTtsCaptureController, CaptureState
from src.diagnostics.widget import DiagnosticCaptureWidget
from src.settings import Settings


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])


def test_diagnostics_widget_starts_and_stops_a_manual_capture(qapp, tmp_path) -> None:
    controller = AppTtsCaptureController()
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    widget = DiagnosticCaptureWidget(
        controller=controller,
        settings=cast("Settings", settings),
        capture_dir=tmp_path,
    )

    assert controller.snapshot().state is CaptureState.IDLE
    assert not widget.stop_button.isEnabled()
    widget.start_capture()
    assert controller.snapshot().state is CaptureState.RECORDING
    assert not widget.start_button.isEnabled()

    controller.record_text("传奇戒指")
    widget.stop_capture()

    assert controller.snapshot().state is CaptureState.SAVED
    assert len(list(tmp_path.glob("*.jsonl"))) == 1
    widget.deleteLater()
