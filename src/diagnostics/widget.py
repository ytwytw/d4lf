"""Opt-in manual capture controls embedded in the Settings window."""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.diagnostics.tts_capture import APP_TTS_CAPTURE, CaptureControllerError, CaptureState
from src.localization import translate
from src.settings import get_settings

if TYPE_CHECKING:
    from src.diagnostics.tts_capture import AppTtsCaptureController
    from src.settings import Settings


class DiagnosticCaptureWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        controller: AppTtsCaptureController = APP_TTS_CAPTURE,
        settings: Settings | None = None,
        capture_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._settings = settings or get_settings()
        self._capture_dir = capture_dir or self._settings.user_dir / "captures" / "manual"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(translate("diagnostics.manual.title"))
        title.setObjectName("setting-title")
        description = QLabel(translate("diagnostics.manual.description"))
        description.setObjectName("description-label")
        description.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setObjectName("diagnostics-status")

        buttons = QHBoxLayout()
        self.start_button = QPushButton(translate("diagnostics.start"))
        self.stop_button = QPushButton(translate("diagnostics.stop"))
        self.open_folder_button = QPushButton(translate("diagnostics.open_folder"))
        self.start_button.clicked.connect(self.start_capture)
        self.stop_button.clicked.connect(self.stop_capture)
        self.open_folder_button.clicked.connect(self.open_capture_folder)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addStretch()

        privacy = QLabel(translate("diagnostics.privacy"))
        privacy.setObjectName("description-label")
        privacy.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)
        layout.addWidget(privacy)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(250)
        self.refresh_status()

    def start_capture(self) -> None:
        try:
            self._controller.start(
                output_dir=self._capture_dir,
                locale=str(self._settings.general.language),
                game_build="unknown",
                metadata={"area": "manual-diagnostics"},
            )
        except CaptureControllerError as error:
            self.status_label.setText(translate("diagnostics.status.error", error=error))
        self.refresh_status()

    def stop_capture(self) -> None:
        try:
            self._controller.stop()
        except CaptureControllerError as error:
            self.status_label.setText(translate("diagnostics.status.error", error=error))
        self.refresh_status()

    def refresh_status(self) -> None:
        snapshot = self._controller.snapshot()
        if snapshot.state is CaptureState.RECORDING:
            text = translate(
                "diagnostics.status.recording",
                count=snapshot.message_count,
                seconds=int(snapshot.elapsed_seconds),
            )
        elif snapshot.state is CaptureState.SAVED:
            text = translate("diagnostics.status.saved", path=snapshot.output_path or "")
        elif snapshot.state is CaptureState.ERROR:
            text = translate(
                "diagnostics.status.error",
                error=snapshot.error or translate("diagnostics.unknown_error"),
            )
        else:
            text = translate("diagnostics.status.idle")
        self.status_label.setText(text)
        self.start_button.setEnabled(snapshot.state is not CaptureState.RECORDING)
        self.stop_button.setEnabled(snapshot.state is CaptureState.RECORDING)

    def open_capture_folder(self) -> None:
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._capture_dir)))


__all__ = ["DiagnosticCaptureWidget"]
