import tkinter as tk

from src.localization import translate
from src.loot import get_filter_colors
from src.overlay.widget.shared import ACCENT, CARD_BG, TEXT, OverlayContract


class _OverlayMenu(OverlayContract):
    def _show_context_menu(self, event):
        """Create and display a persistent settings popup."""
        # Import lazily because lifecycle construction imports this widget.
        # ruff:ignore[import-outside-top-level] - breaks the lifecycle/widget import cycle
        from src.overlay.lifecycle import request_close

        self._destroy_settings_popup()

        if event:
            self._last_menu_pos = (event.x_root, event.y_root)

        popup = tk.Toplevel(self)
        popup.overrideredirect(boolean=True)
        popup.attributes("-topmost", 1)
        popup.configure(bg=CARD_BG, highlightthickness=1, highlightbackground=ACCENT)
        self._settings_popup = popup

        # Header
        header = tk.Label(
            popup,
            text=translate("info.menu.settings"),
            bg=ACCENT,
            fg=CARD_BG,
            font=(self.font_family, self.font_size, "bold"),
        )
        header.pack(fill="x")

        # Visibility Section
        self._create_toggle_btn(popup, translate("info.menu.world_boss"), "show_wb")
        self._create_toggle_btn(popup, translate("info.menu.legion"), "show_legion")
        self._create_toggle_btn(popup, translate("info.menu.helltide"), "show_ht")

        tk.Frame(popup, height=1, bg=ACCENT).pack(fill="x", pady=2)

        self._create_submenu_button(
            popup, translate("info.menu.gold.config"), "gold_stats_submenu", self._build_gold_submenu_content
        ).pack(fill="x")

        self._create_submenu_button(
            popup, translate("info.menu.exp.config"), "exp_stats_submenu", self._build_exp_submenu_content
        ).pack(fill="x")

        self._create_submenu_button(
            popup, translate("info.menu.reset_stats"), "reset_stats_submenu", self._build_reset_submenu_content
        ).pack(fill="x")

        tk.Frame(popup, height=1, bg=ACCENT).pack(fill="x", pady=2)

        # UI Adjustments
        tk.Button(
            popup,
            text=translate(
                "info.menu.orientation",
                orientation=translate(f"info.orientation.{self.orientation}", self.orientation.title()),
            ),
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            anchor="w",
            padx=10,
            pady=5,
            font=(self.font_family, self.font_size),
            activebackground=ACCENT,
            activeforeground=CARD_BG,
            command=lambda: (
                self._toggle_orientation(),
                self._destroy_settings_popup(),
                self._show_context_menu(event=None),
            ),
        ).pack(fill="x")
        tk.Button(
            popup,
            text=translate("info.menu.increase_size"),
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            anchor="w",
            padx=10,
            pady=5,
            font=(self.font_family, self.font_size),
            activebackground=ACCENT,
            activeforeground=CARD_BG,
            command=lambda: (self._change_size(2), self._destroy_settings_popup(), self._show_context_menu(event=None)),
        ).pack(fill="x")
        tk.Button(
            popup,
            text=translate("info.menu.decrease_size"),
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            anchor="w",
            padx=10,
            pady=5,
            font=(self.font_family, self.font_size),
            activebackground=ACCENT,
            activeforeground=CARD_BG,
            command=lambda: (
                self._change_size(-2),
                self._destroy_settings_popup(),
                self._show_context_menu(event=None),
            ),
        ).pack(fill="x")

        # Font Submenu
        def build_font_submenu_content(submenu_frame):
            for font_name in self.FONT_CHOICES:
                self._create_radio_button(
                    submenu_frame, font_name, self.font_family, font_name, self._change_font_family
                ).pack(fill="x")

        self._create_submenu_button(
            popup, translate("info.menu.font"), "font_submenu", build_font_submenu_content
        ).pack(fill="x")

        tk.Frame(popup, height=1, bg=ACCENT).pack(fill="x", pady=2)

        # System Actions
        colors = get_filter_colors()
        for message_id, cmd in [
            ("info.menu.refresh", self._auto_sync),
            ("info.menu.lock", self._toggle_lock),
            ("info.menu.close", request_close),
        ]:
            label = translate(message_id)
            fg_color = TEXT
            if message_id == "info.menu.lock" and self.locked:
                fg_color = colors.matched

            btn = tk.Button(
                popup,
                text=label,
                bg=CARD_BG,
                fg=fg_color,
                bd=0,
                anchor="w",
                padx=10,
                pady=5,
                font=(self.font_family, self.font_size),
                activebackground=ACCENT,
                activeforeground=CARD_BG,
                command=lambda c=cmd, msg_id=message_id: (
                    c(),
                    self._destroy_settings_popup(),
                    self._show_context_menu(event=None) if msg_id != "info.menu.close" else None,
                ),
            )
            btn.pack(fill="x")
        # Position the popup at the mouse click
        popup.geometry(f"+{self._last_menu_pos[0]}+{self._last_menu_pos[1]}")

        # Auto-close logic
        popup.bind("<FocusOut>", self._on_popup_focus_out)  # Use the family focus out handler
        popup.bind("<Escape>", lambda _: (popup.destroy(), self._close_all_submenus()))  # Escape still closes all
        popup.focus_set()
