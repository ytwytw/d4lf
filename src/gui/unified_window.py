import logging
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, override

from PyQt6.QtCore import QEvent, QObject, QPoint, QSettings, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QWidget,
)

from src import __version__
from src.autoupdater import notify_if_update
from src.config.loader import IniConfigLoader
from src.config.reload_groups import (
    DIAGNOSTICS_PAGE_SETTING_KEYS,
    LANGUAGE_SETTING_KEYS,
    LOG_LEVEL_SETTING_KEYS,
    has_any_changed,
)
from src.gui.diagnostics_widget import DiagnosticsWidget
from src.gui.i18n import install_ui_localization, retranslate_open_windows, translate
from src.gui.importer_window import ImporterWindow
from src.gui.models.activity_log_widget import ActivityLogWidget, ANSIConsoleWidget, QtConsoleHandler
from src.gui.profile_editor_window import ProfileEditorWindow
from src.gui.settings_window import ConfigWindow
from src.gui.themes import DARK_THEME_TEMPLATE, LIGHT_THEME_TEMPLATE
from src.logger import apply_log_level, consume_startup_log_records, create_formatter, remove_transient_gui_handlers
from src.logger import setup as setup_logging
from src.scripts.common import get_filter_colors

if TYPE_CHECKING:
    from src.scripts.handler import ScriptHandler

if sys.platform == "win32":
    from src import tts as tts_module
    from src.cam import Cam
    from src.item.filter import Filter
    from src.main import check_for_proper_tts_configuration
    from src.overlay import Overlay
    from src.scripts.handler import ScriptHandler
    from src.utils.window import WindowSpec, start_detecting_window
else:
    tts_module = None

BASE_DIR = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent.parent
)

ICON_PATH = BASE_DIR / "assets" / "logo.png"


def get_asset_path(filename: str) -> Path:
    """Resilient helper to find assets in root/assets or src/assets, handling case sensitivity."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "assets" / filename

    # Search paths: 3 parents (root from gui/) and 2 parents (src from gui/)
    for parent_level in [2, 3]:
        base = Path(__file__).resolve().parents[parent_level]
        # Try exact name, then lowercase version
        for name in [filename, filename.lower()]:
            p = base / "assets" / name
            if p.exists():
                return p
    # Fallback to the root path even if not found
    return Path(__file__).resolve().parents[2] / "assets" / filename


DISCORD_ICON = get_asset_path("Discord.png")
GITHUB_ICON = get_asset_path("Github.png")

LOGGER = logging.getLogger(__name__)


class BackendWorker(QObject):
    finished = pyqtSignal()
    script_handler: ScriptHandler | None = None

    def run(self):
        if sys.platform != "win32":
            LOGGER.info("GUI-only mode is active on non-Windows. Backend runtime is disabled.")
            self.finished.emit()
            return

        Filter().load_files()

        running_from_source = not getattr(sys, "frozen", False)
        if running_from_source:
            LOGGER.debug("Skipping autoupdate check as code is being run from source.")
        else:
            notify_if_update()

        win_spec = WindowSpec(IniConfigLoader().advanced_options.process_name)
        start_detecting_window(win_spec)

        while not Cam().is_offset_set():
            time.sleep(0.2)

        time.sleep(0.5)

        self.script_handler = ScriptHandler()

        check_for_proper_tts_configuration()
        tts_module.start_connection()

        overlay = Overlay()
        overlay.run()

        self.finished.emit()


class UnifiedMainWindow(QMainWindow):
    diagnostics_page_change_requested = pyqtSignal(bool)
    ui_language_change_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._child_windows: dict[str, QMainWindow] = {}
        self._diagnostic_vision_state: bool | None = None
        self.diagnostics_tab: DiagnosticsWidget | None = None
        self._backend_thread: QThread | None = None
        self.worker: BackendWorker | None = None
        self._closing = False
        self._config = IniConfigLoader()
        self.diagnostics_page_change_requested.connect(self._set_diagnostics_page_enabled)
        self.ui_language_change_requested.connect(self.retranslate_ui)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            install_ui_localization(app)
        self._config.register_change_listener(self._on_config_changed_language)
        self._config.register_change_listener(self._on_config_changed_diagnostics_page)

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.apply_theme()
        self._setup_logging()
        self._setup_ui()
        self._setup_tray()
        self.retranslate_ui()
        self._init_backend()
        self.restore_geometry()

        # Polling timer to keep the Dashboard status indicators in sync with the backend
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_dashboard_status)
        self._status_timer.start(500)

    def _setup_logging(self):
        running_from_source = not getattr(sys, "frozen", False)
        root_logger = logging.getLogger()
        adv = self._config.advanced_options

        if not any(getattr(h, "name", "") == "D4LF_FILE" for h in root_logger.handlers):
            setup_logging(
                log_level=adv.log_lvl.value,
                enable_stdout=running_from_source,
                technical=adv.technical_log_info,
                timestamp=adv.log_timestamp,
                buffer_startup=True,
            )

        remove_transient_gui_handlers(root_logger)

        # Single unified Qt handler for both Dashboard and Full Logs
        self.console_handler = QtConsoleHandler()
        self.console_handler.name = "QT_CONSOLE"
        self.console_handler.setFormatter(
            create_formatter(colored=True, technical=adv.technical_log_info, timestamp=adv.log_timestamp)
        )
        self.console_handler.setLevel(adv.log_lvl.value.upper())

        root_logger.addHandler(self.console_handler)
        # Root is always DEBUG; the handlers above (Console/QT) filter based on user settings
        root_logger.setLevel(logging.DEBUG)

        # Apply log level changes live, independently of the backend's wait-for-D4 loop.
        self._config.register_change_listener(self._on_config_changed_log_level)

    def _on_config_changed_log_level(self, changed_keys) -> None:
        if not has_any_changed(changed_keys, LOG_LEVEL_SETTING_KEYS):
            return
        adv = self._config.advanced_options
        new_level = adv.log_lvl.value.upper()
        formatter = create_formatter(colored=True, technical=adv.technical_log_info, timestamp=adv.log_timestamp)
        apply_log_level(new_level, skip_handler_names={"D4LF_FILE"}, formatter=formatter)
        LOGGER.info(
            "Updated log settings (Level: %s, Tech: %s, TS: %s)", new_level, adv.technical_log_info, adv.log_timestamp
        )

    def _on_config_changed_language(self, changed_keys) -> None:
        if has_any_changed(changed_keys, LANGUAGE_SETTING_KEYS):
            self.ui_language_change_requested.emit()

    def _on_config_changed_diagnostics_page(self, changed_keys) -> None:
        if has_any_changed(changed_keys, DIAGNOSTICS_PAGE_SETTING_KEYS):
            self.diagnostics_page_change_requested.emit(self._config.general.show_diagnostics_tab)

    def _setup_ui(self):
        self.setWindowTitle(translate("D4LF - Diablo 4 Loot Filter v{version}", version=__version__))
        self.setMinimumSize(800, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.activity_tab = ActivityLogWidget(parent=self)
        self.console_output = ANSIConsoleWidget()

        self.tabs.addTab(self.activity_tab, translate("Dashboard"))
        self.tabs.addTab(self.console_output, translate("Full Logs"))
        self._set_diagnostics_page_enabled(self._config.general.show_diagnostics_tab)
        self._setup_tab_corner_widgets()

        # Both tabs receive the same unified stream
        self.console_handler.log_signal.connect(self.console_output.append_ansi_text)
        self.console_handler.log_signal.connect(self.activity_tab.log_viewer.append_ansi_text)

        self.emit_startup_direct_to_console()
        self._emit_startup_logs()
        self._emit_deferred_config_cleanup_logs(self._config)

    def _set_diagnostics_page_enabled(self, enabled: bool) -> None:
        if enabled:
            self._show_diagnostics_tab()
        else:
            self._hide_diagnostics_tab()

    def _show_diagnostics_tab(self) -> None:
        if self.diagnostics_tab is not None:
            return
        self.diagnostics_tab = DiagnosticsWidget(
            parent=self,
            on_capture_started=self._enable_vision_for_diagnostic_capture,
            on_capture_ended=self._restore_vision_after_diagnostic_capture,
        )
        self.tabs.addTab(self.diagnostics_tab, translate("Diagnostics"))
        LOGGER.info("Enabled the diagnostic capture tab")

    def _hide_diagnostics_tab(self) -> None:
        diagnostics_tab = self.diagnostics_tab
        if diagnostics_tab is None:
            return
        diagnostics_tab.shutdown()
        index = self.tabs.indexOf(diagnostics_tab)
        if index >= 0:
            if self.tabs.currentWidget() is diagnostics_tab:
                self.tabs.setCurrentWidget(self.activity_tab)
            self.tabs.removeTab(index)
        diagnostics_tab.deleteLater()
        self.diagnostics_tab = None
        LOGGER.info("Disabled the diagnostic capture tab")

    def _setup_tab_corner_widgets(self):
        """Add social buttons to the top right of the tab bar."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 15, 0)
        layout.setSpacing(15)

        # System Status Indicators
        if sys.platform == "win32":
            self.vision_indicator = QLabel(translate("Vision Mode: STOPPED"))
            self.vision_indicator.setStyleSheet("color: #ff4d4d; font-weight: bold; font-size: 10pt;")
            self.tts_indicator = QLabel(translate("TTS: Disconnected"))
            self.tts_indicator.setStyleSheet("color: #ff4d4d; font-weight: bold; font-size: 10pt;")
        else:
            self.vision_indicator = QLabel(translate("Vision Mode: Disabled (GUI-only)"))
            self.vision_indicator.setStyleSheet("color: #b0b0b0; font-weight: bold; font-size: 10pt;")
            self.tts_indicator = QLabel(translate("TTS: Disabled (GUI-only)"))
            self.tts_indicator.setStyleSheet("color: #b0b0b0; font-weight: bold; font-size: 10pt;")

        layout.addWidget(self.vision_indicator)
        layout.addWidget(self.tts_indicator)

        discord_btn = QPushButton()
        self._setup_social_button(discord_btn, DISCORD_ICON, "https://discord.gg/YyzaPhAN6T")
        github_btn = QPushButton()
        self._setup_social_button(github_btn, GITHUB_ICON, "https://github.com/ytwytw/d4lf")

        layout.addWidget(discord_btn)
        layout.addWidget(github_btn)
        self.tabs.setCornerWidget(container, Qt.Corner.TopRightCorner)

    def _setup_social_button(self, btn: QPushButton, icon_path: Path, url: str):
        # Double check existence and check for lowercase fallback on-the-fly
        final_path = icon_path
        if not final_path.exists():
            alt_path = icon_path.parent / icon_path.name.lower()
            if alt_path.exists():
                final_path = alt_path

        if final_path.exists():
            btn.setIcon(QIcon(str(final_path)))
            btn.setIconSize(QSize(24, 24))
        else:
            btn.setText("D" if "discord" in url else "G")
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(url)
        btn.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; } QPushButton:hover { background-color: #333; border-radius: 4px; }"
        )
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))

    def _refresh_dashboard_status(self):
        """Poll backend states and update the Dashboard labels."""
        self.update_tts_status(tts_module.CONNECTED if tts_module is not None else None)
        worker = self.worker
        handler = worker.script_handler if worker is not None else None
        if handler is not None:
            self.update_vision_status(handler.vision_mode.running())

    def _enable_vision_for_diagnostic_capture(self) -> None:
        worker = self.worker
        handler = worker.script_handler if worker is not None else None
        if handler is None:
            self._diagnostic_vision_state = None
            return
        handler.stop_active_game_input()
        self._diagnostic_vision_state = handler.vision_mode.running()
        if not self._diagnostic_vision_state:
            handler.vision_mode.start()
            LOGGER.info("Started vision mode for diagnostic TTS capture")

    def _restore_vision_after_diagnostic_capture(self) -> None:
        previous_state = self._diagnostic_vision_state
        self._diagnostic_vision_state = None
        if previous_state is None or self._closing:
            return

        worker = self.worker
        handler = worker.script_handler if worker is not None else None
        if handler is None:
            return
        is_running = handler.vision_mode.running()
        if previous_state and not is_running:
            handler.vision_mode.start()
        elif not previous_state and is_running:
            handler.vision_mode.stop()
        LOGGER.info("Restored vision mode state after diagnostic TTS capture")

    def update_vision_status(self, is_running: bool | None):
        if is_running is None:
            self.vision_indicator.setText(translate("Vision Mode: Disabled (GUI-only)"))
            self.vision_indicator.setStyleSheet("color: #b0b0b0; font-weight: bold; font-size: 10pt;")
            return
        if is_running:
            self.vision_indicator.setText(translate("Vision Mode: RUNNING"))
            self.vision_indicator.setStyleSheet("color: #23fc5d; font-weight: bold; font-size: 10pt;")
        else:
            self.vision_indicator.setText(translate("Vision Mode: STOPPED"))
            self.vision_indicator.setStyleSheet("color: #ff4d4d; font-weight: bold; font-size: 10pt;")

    def update_tts_status(self, connected: bool | None):
        if connected is None:
            self.tts_indicator.setText(translate("TTS: Disabled (GUI-only)"))
            self.tts_indicator.setStyleSheet("color: #b0b0b0; font-weight: bold; font-size: 10pt;")
            return
        if connected:
            self.tts_indicator.setText(translate("TTS: Connected"))
            self.tts_indicator.setStyleSheet("color: #23fc5d; font-weight: bold; font-size: 10pt;")
        else:
            self.tts_indicator.setText(translate("TTS: Disconnected"))
            self.tts_indicator.setStyleSheet("color: #ff4d4d; font-weight: bold; font-size: 10pt;")

    def _init_backend(self):
        if sys.platform != "win32":
            self._backend_thread = None
            self.worker = None
            self.update_vision_status(None)
            self.update_tts_status(None)
            return

        backend_thread = QThread()
        worker = BackendWorker()
        worker.moveToThread(backend_thread)
        backend_thread.started.connect(worker.run)
        worker.finished.connect(backend_thread.quit)
        self._backend_thread = backend_thread
        self.worker = worker
        backend_thread.start()

    def _show_singleton_modal(self, key: str, window_class, *args, **kwargs):
        existing_window = self._child_windows.get(key)

        # If window exists and is visible, just bring it to front
        if existing_window is not None and existing_window.isVisible():
            existing_window.raise_()
            existing_window.activateWindow()
            return existing_window
        win = window_class(*args, **kwargs)
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        win.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._child_windows[key] = win
        win.destroyed.connect(lambda: self._child_windows.pop(key, None))

        win.show()
        return win

    def _emit_deferred_config_cleanup_logs(self, config):
        for record in config.consume_deferred_cleanup_log_records():
            if not logging.getLogger(record.name).isEnabledFor(record.levelno):
                continue
            if record.levelno >= self.console_handler.level:
                self.console_handler.handle(record)

    def _emit_startup_logs(self):
        for record in consume_startup_log_records():
            if not logging.getLogger(record.name).isEnabledFor(record.levelno):
                continue
            if record.levelno >= self.console_handler.level:
                self.console_handler.handle(record)

    def open_import_dialog(self):
        win = self._show_singleton_modal("importer", ImporterWindow)
        win.import_completed.connect(self.activity_tab.refresh_profiles, Qt.ConnectionType.UniqueConnection)

    def open_settings_dialog(self):
        self._show_singleton_modal(
            "config",
            ConfigWindow,
            theme_changed_callback=self.apply_theme,
            language_changed_callback=self.retranslate_ui,
        )

    def open_profile_editor(self, profile_name: str | None = None):
        self._show_singleton_modal("editor", ProfileEditorWindow, profile_name=profile_name)

    def restore_geometry(self):
        settings = QSettings("d4lf", "mainwindow")

        size = settings.value("size", QSize(1000, 800))
        pos = settings.value("pos", QPoint(100, 100))
        maximized = settings.value("maximized", "false") == "true"

        self.resize(size)
        self.move(pos)

        if maximized:
            self.showMaximized()
        self.tabs.setCurrentIndex(settings.value("selected_tab", 0, int))
        # Using False as a positional argument for defaultValue is required by the QSettings API
        self.activity_tab.minimize_to_tray_cb.setChecked(
            settings.value("minimize_to_tray", False, type=bool)  # noqa: FBT003
        )

    def save_geometry(self):
        settings = QSettings("d4lf", "mainwindow")

        if not self.isMaximized():
            settings.setValue("size", self.size())
            settings.setValue("pos", self.pos())

        settings.setValue("maximized", self.isMaximized())
        settings.setValue("selected_tab", self.tabs.currentIndex())
        settings.setValue("minimize_to_tray", self.activity_tab.minimize_to_tray_cb.isChecked())

    def _setup_tray(self):
        """Initialize the system tray icon and its context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        if ICON_PATH.exists():
            self.tray_icon.setIcon(QIcon(str(ICON_PATH)))

        tray_menu = QMenu(self)
        self.restore_action = QAction(translate("Restore"), tray_menu)
        self.restore_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(self.restore_action)

        tray_menu.addSeparator()

        self.exit_action = QAction(translate("Exit"), tray_menu)
        self.exit_action.triggered.connect(self.close)
        tray_menu.addAction(self.exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.setToolTip(translate("D4 Loot Filter"))
        self.tray_icon.show()

    def _on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()

    @override
    def changeEvent(self, a0: QEvent | None):
        # PyQt exposes `a0` as a keyword, so the override must retain that public name.
        event = a0
        if (
            event is not None
            and event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self.activity_tab.minimize_to_tray_cb.isChecked()
        ):
            self.hide()
        super().changeEvent(event)

    @override
    def closeEvent(self, a0: QCloseEvent | None):
        # PyQt exposes `a0` as a keyword, so the override must retain that public name.
        event = a0
        self._closing = True
        diagnostics_tab = getattr(self, "diagnostics_tab", None)
        if diagnostics_tab is not None:
            diagnostics_tab.shutdown()
        for win in list(self._child_windows.values()):
            with suppress(Exception):
                win.close()

        self.save_geometry()
        root_logger = logging.getLogger()
        with suppress(Exception):
            root_logger.removeHandler(self.console_handler)

        super().closeEvent(event)

    def emit_startup_direct_to_console(self):
        banner = (
            "═══════════════════════════════════════════════════════════════════════════════\n"
            "D4LF - Diablo 4 Loot Filter\n"
            "═══════════════════════════════════════════════════════════════════════════════"
        )
        self.console_output.append_ansi_text(banner)
        self.console_output.append_ansi_text("")

    def retranslate_ui(self) -> None:
        self.setWindowTitle(translate("D4LF - Diablo 4 Loot Filter v{version}", version=__version__))
        if hasattr(self, "tabs"):
            self.tabs.setTabText(self.tabs.indexOf(self.activity_tab), translate("Dashboard"))
            self.tabs.setTabText(self.tabs.indexOf(self.console_output), translate("Full Logs"))
            self.activity_tab.retranslate_ui()
            if self.diagnostics_tab is not None:
                self.tabs.setTabText(self.tabs.indexOf(self.diagnostics_tab), translate("Diagnostics"))
                self.diagnostics_tab.retranslate_ui()
            self.update_tts_status(tts_module.CONNECTED if tts_module is not None else None)
            worker = self.worker
            handler = worker.script_handler if worker is not None else None
            if handler is not None:
                self.update_vision_status(handler.vision_mode.running())
            else:
                self.update_vision_status(None if sys.platform != "win32" else False)
        if hasattr(self, "tray_icon"):
            self.restore_action.setText(translate("Restore"))
            self.exit_action.setText(translate("Exit"))
            self.tray_icon.setToolTip(translate("D4 Loot Filter"))
        for window in self._child_windows.values():
            retranslate_ui = getattr(window, "retranslate_ui", None)
            if callable(retranslate_ui):
                retranslate_ui()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            retranslate_open_windows(app)

    def apply_theme(self):
        theme_name = IniConfigLoader().general.theme
        accent_color = get_filter_colors().matched
        template = DARK_THEME_TEMPLATE if theme_name == "dark" else LIGHT_THEME_TEMPLATE
        stylesheet = template.replace("{accent}", accent_color)

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(stylesheet)
