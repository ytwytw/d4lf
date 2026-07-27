import logging
import sys
from pathlib import Path
from typing import override

from PyQt6.QtCore import QPoint, QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QMainWindow

from src.localization import translate
from src.settings import LANGUAGE_SETTING_KEYS, get_settings, has_any_changed
from src.settings.tab import ConfigTab

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]

ICON_PATH = BASE_DIR / "assets" / "logo.png"
LOGGER = logging.getLogger(__name__)


class ConfigWindow(QMainWindow):
    """Standalone window for Config/Settings."""

    language_changed_signal = pyqtSignal()

    def __init__(self, parent=None, theme_changed_callback=None):
        super().__init__(parent)

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.theme_changed_callback = theme_changed_callback
        self.settings = QSettings("d4lf", "config")
        self._config = get_settings()
        self.language_changed_signal.connect(self._on_language_changed)
        self._config.register_change_listener(self._queue_config_change)

        self.setWindowTitle(translate("settings.title"))

        self.resize(self.settings.value("size", QSize(650, 800)))
        self.move(self.settings.value("pos", QPoint(0, 0)))

        if self.settings.value("maximized", "false") == "true":
            self.showMaximized()

        # Create initial config tab
        self.config_tab = ConfigTab(theme_changed_callback=self._on_theme_changed)
        self.setCentralWidget(self.config_tab)

    def _on_theme_changed(self):
        if self.theme_changed_callback:
            self.theme_changed_callback()

        # Rebuild the tab so the settings window updates visually too
        self._rebuild_tab()

    def _rebuild_tab(self):
        current_idx = self.config_tab.nav_list.currentRow()
        old_tab = self.config_tab
        self.config_tab = ConfigTab(theme_changed_callback=self._on_theme_changed)
        self.setCentralWidget(self.config_tab)
        if current_idx >= 0:
            self.config_tab.nav_list.setCurrentRow(current_idx)
        old_tab.deleteLater()

    def _queue_config_change(self, changed_keys) -> None:
        if has_any_changed(changed_keys, LANGUAGE_SETTING_KEYS):
            self.language_changed_signal.emit()

    def _on_language_changed(self) -> None:
        self.setWindowTitle(translate("settings.title"))
        self._rebuild_tab()

    @override
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Save window size/position."""
        if not self.isMaximized():
            self.settings.setValue("size", self.size())
            self.settings.setValue("pos", self.pos())
        self.settings.setValue("maximized", self.isMaximized())
        self._config.unregister_change_listener(self._queue_config_change)
        if a0 is not None:
            a0.accept()
