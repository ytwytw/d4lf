"""Live localization behavior for the unified application window."""

from typing import TYPE_CHECKING, Any

from src import __version__
from src.localization import translate
from src.settings import LANGUAGE_SETTING_KEYS, has_any_changed


class UnifiedWindowLocalization:
    _config: Any
    locale_changed_signal: Any
    activity_tab: Any
    console_output: Any
    exit_action: Any
    restore_action: Any
    tabs: Any
    tray_icon: Any

    if TYPE_CHECKING:

        def setWindowTitle(self, a0: str | None) -> None: ...  # ruff:ignore[invalid-function-name]

    def _setup_localization(self) -> None:
        self.locale_changed_signal.connect(self._retranslate_ui)
        self._config.register_change_listener(self._on_config_changed_language)
        self._retranslate_ui()

    def _on_config_changed_language(self, changed_keys) -> None:
        if has_any_changed(changed_keys, LANGUAGE_SETTING_KEYS):
            self.locale_changed_signal.emit()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(translate("app.title", version=__version__))
        self.tabs.setTabText(self.tabs.indexOf(self.activity_tab), translate("tabs.dashboard"))
        self.tabs.setTabText(self.tabs.indexOf(self.console_output), translate("tabs.full_logs"))
        self.restore_action.setText(translate("tray.restore"))
        self.exit_action.setText(translate("tray.exit"))
        self.tray_icon.setToolTip(translate("app.tray_title"))
        self.activity_tab.retranslate_ui()
