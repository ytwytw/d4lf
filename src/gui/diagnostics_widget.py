from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import psutil
from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from src import __version__, tts
from src.config.loader import IniConfigLoader
from src.config.settings_models import SUPPORTED_LANGUAGES
from src.diagnostics.auto_failure_capture import set_detected_game_build
from src.diagnostics.tts_capture import (
    APP_TTS_CAPTURE,
    AppTtsCaptureController,
    CaptureControllerError,
    CaptureResult,
    CaptureState,
)
from src.gui.i18n import language_label, translate

if TYPE_CHECKING:
    from collections.abc import Callable

_get_file_version_info: Callable[[str, str], object] | None = None
VERSION_INFO_ERRORS: tuple[type[BaseException], ...] = (OSError,)
if sys.platform == "win32":
    try:
        import pywintypes as _pywintypes
        import win32api as _win32api
    except ImportError:  # pragma: no cover - pywin32 is an optional Windows dependency
        pass
    else:
        _get_file_version_info = _win32api.GetFileVersionInfo
        VERSION_INFO_ERRORS = (OSError, _pywintypes.error)

LOGGER = logging.getLogger(__name__)

BASE_DIR = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent.parent
)
GAME_BUILD_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
GAME_BUILD_SEARCH_PATTERN = re.compile(r"(\d+)[.,]\s*(\d+)[.,]\s*(\d+)[.,]\s*(\d+)")

CAPTURE_CATEGORIES = (
    ("Core equipment", "core"),
    ("Talisman equipment", "talisman"),
    ("Sigils and tributes", "extended-filters"),
    ("Custom", "custom"),
)
CAPTURE_AREAS = (
    ("Inventory", "inventory"),
    ("Equipped", "equipped"),
    ("Vendor", "vendor"),
    ("Stash", "stash"),
    ("Mixed equipment", "mixed-equipment"),
)


def parse_game_build(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = GAME_BUILD_SEARCH_PATTERN.search(value)
    return ".".join(match.groups()) if match else None


def _report_frame_count(report: dict[str, object]) -> int:
    frame_count = report.get("frame_count")
    if not isinstance(frame_count, int):
        msg = "Diagnostic replay report did not contain an integer frame_count"
        raise TypeError(msg)
    return frame_count


def game_build_from_version_resource(executable: str) -> str | None:
    get_file_version_info = _get_file_version_info
    if get_file_version_info is None:
        return None
    translations: list[tuple[int, int]] = []
    try:
        raw_translations = get_file_version_info(executable, r"\VarFileInfo\Translation")
    except VERSION_INFO_ERRORS:
        raw_translations = []
    if isinstance(raw_translations, (list, tuple)):
        translations.extend(
            (value[0], value[1])
            for value in raw_translations
            if (
                isinstance(value, (list, tuple))
                and len(value) == 2
                and isinstance(value[0], int)
                and isinstance(value[1], int)
            )
        )
    translations.append((0x0409, 0x04B0))

    for language, codepage in dict.fromkeys(translations):
        for field in ("ProductVersion", "FileVersion"):
            query = rf"\StringFileInfo\{language:04x}{codepage:04x}\{field}"
            try:
                if build := parse_game_build(get_file_version_info(executable, query)):
                    return build
            except VERSION_INFO_ERRORS:
                continue
    return None


def detect_running_game_build(process_name: str) -> str | None:
    if _get_file_version_info is None:
        return None

    for process in psutil.process_iter(["name", "exe"]):
        try:
            if (process.info.get("name") or "").casefold() != process_name.casefold():
                continue
            executable = process.info.get("exe")
            if not executable:
                continue
            return game_build_from_version_resource(executable)
        except OSError, psutil.Error:
            continue
    return None


class DiagnosticsWidget(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        controller: AppTtsCaptureController = APP_TTS_CAPTURE,
        capture_dir: Path | None = None,
        assets_root: Path | None = None,
        initial_locale: str | None = None,
        process_name: str | None = None,
        on_capture_started: Callable[[], None] | None = None,
        on_capture_ended: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        config = IniConfigLoader()
        self._config = config
        self._controller = controller
        self._capture_dir = capture_dir or config.user_dir / "captures"
        self._assets_root = assets_root or BASE_DIR / "assets" / "lang"
        self._process_name = process_name or config.advanced_options.process_name
        self._on_capture_started = on_capture_started
        self._on_capture_ended = on_capture_ended
        self._capture_lifecycle_active = False
        self._last_output_path: Path | None = None
        self._last_report_path: Path | None = None
        self._last_replay_error: str | None = None
        self._last_frame_count: int | None = None

        self._setup_ui(initial_locale or config.general.language)
        self._detect_build(show_message=False)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(250)
        self.refresh_status()

    @property
    def last_output_path(self) -> Path | None:
        return self._last_output_path

    @property
    def last_report_path(self) -> Path | None:
        return self._last_report_path

    def _setup_ui(self, initial_locale: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)
        style = self.style()

        status_layout = QHBoxLayout()
        self.capture_status_label = QLabel(translate("Capture: Idle"))
        self.capture_status_label.setStyleSheet("font-weight: bold;")
        self.tts_status_label = QLabel(translate("TTS: Disconnected"))
        self.message_count_label = QLabel(translate("{count} messages", count=0))
        status_layout.addWidget(self.capture_status_label)
        status_layout.addSpacing(18)
        status_layout.addWidget(self.tts_status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.message_count_label)
        layout.addLayout(status_layout)

        fields = QGridLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(12)

        self.locale_combo = QComboBox()
        for locale in sorted(SUPPORTED_LANGUAGES):
            self.locale_combo.addItem(language_label(locale), locale)
        initial_index = self.locale_combo.findData(initial_locale)
        self.locale_combo.setCurrentIndex(max(0, initial_index))

        self.category_combo = QComboBox()
        for label, value in CAPTURE_CATEGORIES:
            self.category_combo.addItem(translate(label), value)

        self.area_combo = QComboBox()
        for label, value in CAPTURE_AREAS:
            self.area_combo.addItem(translate(label), value)
        self.area_combo.setCurrentIndex(self.area_combo.findData("mixed-equipment"))

        self.build_input = QLineEdit()
        self.build_input.setPlaceholderText("3.1.0.72698")
        self.build_input.setClearButtonEnabled(True)
        self.detect_build_button = QPushButton()
        if style is not None:
            self.detect_build_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.detect_build_button.setFixedSize(34, 34)
        self.detect_build_button.setToolTip(translate("Detect build from the running Diablo IV process"))
        self.detect_build_button.clicked.connect(lambda: self._detect_build(show_message=True))
        build_layout = QHBoxLayout()
        build_layout.setContentsMargins(0, 0, 0, 0)
        build_layout.addWidget(self.build_input)
        build_layout.addWidget(self.detect_build_button)

        self.locale_label = QLabel(translate("Locale"))
        self.game_build_label = QLabel(translate("Game build"))
        self.category_label = QLabel(translate("Capture category"))
        self.area_label = QLabel(translate("Game area"))
        fields.addWidget(self.locale_label, 0, 0)
        fields.addWidget(self.locale_combo, 0, 1)
        fields.addWidget(self.game_build_label, 0, 2)
        fields.addLayout(build_layout, 0, 3)
        fields.addWidget(self.category_label, 1, 0)
        fields.addWidget(self.category_combo, 1, 1)
        fields.addWidget(self.area_label, 1, 2)
        fields.addWidget(self.area_combo, 1, 3)
        fields.setColumnStretch(1, 1)
        fields.setColumnStretch(3, 1)
        layout.addLayout(fields)

        actions = QHBoxLayout()
        self.start_button = QPushButton(translate("Start Capture"))
        self.start_button.setObjectName("primary")
        if style is not None:
            self.start_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.start_button.clicked.connect(self.start_capture)
        self.stop_button = QPushButton(translate("Stop and Save"))
        if style is not None:
            self.stop_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_capture)
        self.open_folder_button = QPushButton(translate("Open Folder"))
        if style is not None:
            self.open_folder_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.open_folder_button.clicked.connect(self.open_capture_folder)
        for button in (self.start_button, self.stop_button, self.open_folder_button):
            button.setFixedHeight(36)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)

        output_grid = QGridLayout()
        output_grid.setHorizontalSpacing(12)
        output_grid.setVerticalSpacing(10)
        self.output_path_field = QLineEdit()
        self.output_path_field.setReadOnly(True)
        self.report_path_field = QLineEdit()
        self.report_path_field.setReadOnly(True)
        self.raw_capture_label = QLabel(translate("Raw capture"))
        self.replay_report_label = QLabel(translate("Replay report"))
        output_grid.addWidget(self.raw_capture_label, 0, 0)
        output_grid.addWidget(self.output_path_field, 0, 1)
        output_grid.addWidget(self.replay_report_label, 1, 0)
        output_grid.addWidget(self.report_path_field, 1, 1)
        output_grid.setColumnStretch(1, 1)
        layout.addLayout(output_grid)
        layout.addStretch()

    def start_capture(self) -> None:
        game_build = self.build_input.text().strip()
        if not GAME_BUILD_PATTERN.fullmatch(game_build):
            QMessageBox.warning(
                self, translate("Invalid game build"), translate("Enter the exact four-part Diablo IV game build.")
            )
            return
        set_detected_game_build(game_build)

        locale = str(self.locale_combo.currentData())
        category = str(self.category_combo.currentData())
        area = str(self.area_combo.currentData())
        try:
            snapshot = self._controller.start(
                output_dir=self._capture_dir,
                locale=locale,
                game_build=game_build,
                category=category,
                metadata={"area": area, "app_version": __version__, "capture_source": "desktop-app"},
            )
        except CaptureControllerError as error:
            QMessageBox.critical(self, translate("Capture failed"), str(error))
            return

        self._last_output_path = snapshot.output_path
        self._last_report_path = None
        self._last_replay_error = None
        self._last_frame_count = None
        self.output_path_field.setText(str(snapshot.output_path or ""))
        self.report_path_field.clear()
        self._capture_lifecycle_active = True
        if self._on_capture_started is not None:
            try:
                self._on_capture_started()
            except Exception:
                LOGGER.exception("Could not prepare vision mode for diagnostic capture")
        LOGGER.info("Started diagnostic TTS capture: %s", snapshot.output_path)
        self.refresh_status()

    def stop_capture(self, *, show_errors: bool = True) -> CaptureResult | None:
        try:
            result = self._controller.stop()
        except CaptureControllerError as error:
            if not self._controller.is_active:
                self._finish_capture_lifecycle()
            if show_errors:
                QMessageBox.critical(self, translate("Capture failed"), str(error))
            else:
                LOGGER.error("Could not finalize diagnostic TTS capture: %s", error)
            return None

        self._finish_capture_lifecycle()
        self._last_output_path = result.output_path
        self.output_path_field.setText(str(result.output_path))
        self._last_report_path = None
        self._last_replay_error = None
        self._last_frame_count = None
        if result.message_count:
            self._create_replay_report(result)
        else:
            self._last_replay_error = "No TTS messages were received; raw capture is empty."
        LOGGER.info("Saved %s diagnostic TTS messages to %s", result.message_count, result.output_path)
        self.refresh_status()
        return result

    def _create_replay_report(self, result: CaptureResult) -> None:
        # Keep the offline parser out of the normal App startup path.
        report_path = result.output_path.with_name(f"{result.output_path.stem}-report.json")
        try:
            from src.tools.tts_replay import replay_capture, write_report  # noqa: PLC0415

            report = replay_capture(result.output_path, self._assets_root / result.locale)
            frame_count = _report_frame_count(report)
            write_report(report_path, report)
        except Exception as error:
            self._last_replay_error = str(error)
            LOGGER.exception("Raw diagnostic capture was saved, but replay failed")
            return
        self._last_report_path = report_path
        self._last_frame_count = frame_count
        self.report_path_field.setText(str(report_path))
        LOGGER.info("Saved diagnostic replay report with %s frames to %s", self._last_frame_count, report_path)

    def refresh_status(self) -> None:
        snapshot = self._controller.snapshot()
        if self._capture_lifecycle_active and snapshot.state != CaptureState.RECORDING:
            self._finish_capture_lifecycle()
        connected = tts.CONNECTED
        self.tts_status_label.setText(translate("TTS: Connected") if connected else translate("TTS: Disconnected"))
        self.tts_status_label.setStyleSheet(
            "color: #23fc5d; font-weight: bold;" if connected else "color: #ff4d4d; font-weight: bold;"
        )

        recording = snapshot.state == CaptureState.RECORDING
        self.start_button.setEnabled(not recording)
        self.stop_button.setEnabled(recording)
        for control in (
            self.locale_combo,
            self.category_combo,
            self.area_combo,
            self.build_input,
            self.detect_build_button,
        ):
            control.setEnabled(not recording)

        if recording:
            self.capture_status_label.setText(
                translate("Capture: Recording ({elapsed})", elapsed=self._format_elapsed(snapshot.elapsed_seconds))
            )
            self.capture_status_label.setToolTip("")
            self.capture_status_label.setStyleSheet("color: #ff4d4d; font-weight: bold;")
        elif snapshot.state == CaptureState.ERROR:
            self.capture_status_label.setText(translate("Capture: Error"))
            self.capture_status_label.setToolTip(snapshot.error or "Unknown capture error")
            self.capture_status_label.setStyleSheet("color: #ff4d4d; font-weight: bold;")
        elif snapshot.state == CaptureState.SAVED:
            if self._last_replay_error:
                self.capture_status_label.setText(translate("Capture: Saved, replay unavailable"))
                self.capture_status_label.setToolTip(self._last_replay_error)
                self.capture_status_label.setStyleSheet("color: #fca503; font-weight: bold;")
            elif self._last_frame_count is not None:
                self.capture_status_label.setText(
                    translate("Capture: Saved - {frames} item frames", frames=self._last_frame_count)
                )
                self.capture_status_label.setToolTip("")
                self.capture_status_label.setStyleSheet("color: #23fc5d; font-weight: bold;")
            else:
                self.capture_status_label.setText(translate("Capture: Saved"))
                self.capture_status_label.setToolTip("")
                self.capture_status_label.setStyleSheet("color: #23fc5d; font-weight: bold;")
        else:
            self.capture_status_label.setText(translate("Capture: Idle"))
            self.capture_status_label.setToolTip("")
            self.capture_status_label.setStyleSheet("font-weight: bold;")
        self.message_count_label.setText(translate("{count} messages", count=snapshot.message_count))

    def _detect_build(self, *, show_message: bool) -> None:
        detected = detect_running_game_build(self._process_name)
        if detected:
            self.build_input.setText(detected)
            set_detected_game_build(detected)
            return
        if show_message:
            QMessageBox.information(
                self,
                translate("Game build not detected"),
                translate("Start Diablo IV, then try again, or enter the exact four-part build manually."),
            )

    def open_capture_folder(self) -> None:
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._capture_dir)))

    def shutdown(self) -> None:
        if self._controller.is_active:
            self.stop_capture(show_errors=False)
        self._finish_capture_lifecycle()

    def _finish_capture_lifecycle(self) -> None:
        if not self._capture_lifecycle_active:
            return
        self._capture_lifecycle_active = False
        if self._on_capture_ended is None:
            return
        try:
            self._on_capture_ended()
        except Exception:
            LOGGER.exception("Could not restore vision mode after diagnostic capture")

    def retranslate_ui(self) -> None:
        for index in range(self.locale_combo.count()):
            self.locale_combo.setItemText(index, language_label(str(self.locale_combo.itemData(index))))
        category_labels = {value: label for label, value in CAPTURE_CATEGORIES}
        for index in range(self.category_combo.count()):
            value = str(self.category_combo.itemData(index))
            self.category_combo.setItemText(index, translate(category_labels[value]))
        area_labels = {value: label for label, value in CAPTURE_AREAS}
        for index in range(self.area_combo.count()):
            value = str(self.area_combo.itemData(index))
            self.area_combo.setItemText(index, translate(area_labels[value]))
        if not self._controller.is_active:
            language_index = self.locale_combo.findData(self._config.general.language)
            if language_index >= 0:
                self.locale_combo.setCurrentIndex(language_index)
        self.locale_label.setText(translate("Locale"))
        self.game_build_label.setText(translate("Game build"))
        self.category_label.setText(translate("Capture category"))
        self.area_label.setText(translate("Game area"))
        self.start_button.setText(translate("Start Capture"))
        self.stop_button.setText(translate("Stop and Save"))
        self.open_folder_button.setText(translate("Open Folder"))
        self.raw_capture_label.setText(translate("Raw capture"))
        self.replay_report_label.setText(translate("Replay report"))
        self.detect_build_button.setToolTip(translate("Detect build from the running Diablo IV process"))
        self.refresh_status()

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        minutes, remaining_seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{remaining_seconds:02d}"
