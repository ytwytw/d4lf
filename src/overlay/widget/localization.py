"""Live localization for the information overlay."""

from typing import Any

from src.desktop import call_on_ui_thread
from src.localization import translate
from src.overlay.widget.shared import OverlayContract
from src.settings import LANGUAGE_SETTING_KEYS, get_settings, has_any_changed


class _OverlayLocalization(OverlayContract):
    def _setup_localization(self) -> None:
        self._locale_config = get_settings()
        self._locale_config.register_change_listener(self._queue_language_change)
        self._retranslate_ui()

    def _queue_language_change(self, changed_keys) -> None:
        if has_any_changed(changed_keys, LANGUAGE_SETTING_KEYS):
            call_on_ui_thread(self._retranslate_ui)

    def _retranslate_ui(self) -> None:
        if getattr(self, "_closing", False):
            return
        self.title(translate("info.title"))
        for label, message_id in (
            (self.lbl_wb, "info.timer.world_boss"),
            (self.lbl_legion, "info.timer.legion"),
            (self.lbl_ht, "info.timer.helltide"),
        ):
            label.config(text=translate(message_id))
        self._repack()
        self._destroy_settings_popup()
        self._close_all_submenus()

    def _stop_localization(self) -> None:
        config: Any = getattr(self, "_locale_config", None)
        if config is not None:
            config.unregister_change_listener(self._queue_language_change)
