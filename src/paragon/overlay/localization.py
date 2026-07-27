"""Live localization behavior for the Paragon overlay."""

import tkinter as tk
from contextlib import suppress

from src.desktop import is_alive
from src.localization import translate
from src.paragon.shared import OverlayContract


class OverlayLocalizationMixin(OverlayContract):
    def _apply_live_language_change(self) -> None:
        """Retranslate owned text and rebuild locale-dependent popup content."""
        if not is_alive(self):
            return

        self.title(translate("paragon.title"))
        self.lbl_mode.config(
            text=translate("paragon.view.compact" if self._cfg.is_collapsed else "paragon.view.full")
        )
        self.btn_settings.config(text=f"{translate('paragon.settings')}⚙ ▼")
        self.btn_build_menu.config(text=f"{translate('paragon.builds')} ▼")

        self._close_build_dropdown()
        self._close_settings_dropdown()
        popup = getattr(self, "_settings_popup", None)
        self._settings_popup = None
        self._settings_popup_refresh = None
        if isinstance(popup, tk.Frame):
            with suppress(Exception):
                popup.destroy()

        self._refresh_lists()
        self.redraw()
