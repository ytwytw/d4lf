import tkinter as tk
from typing import Protocol

from src.localization import translate
from src.loot import get_filter_colors
from src.overlay.widget.shared import ACCENT, CARD_BG, TEXT, OverlayContract


class _ContextMenuEvent(Protocol):
    x_root: int
    y_root: int


class _OverlayMenu(OverlayContract):
    def _show_context_menu(self, event: _ContextMenuEvent | None) -> None:
        """Create and display a persistent settings popup."""
        self._destroy_settings_popup()
        if event:
            self._last_menu_pos = (event.x_root, event.y_root)

        popup = tk.Toplevel(self)
        popup.overrideredirect(boolean=True)
        popup.attributes("-topmost", 1)
        popup.configure(bg=CARD_BG, highlightthickness=1, highlightbackground=ACCENT)
        self._settings_popup = popup

        header = tk.Label(
            popup,
            text=translate("info.menu.settings"),
            bg=ACCENT,
            fg=CARD_BG,
            font=(self.font_family, self.font_size, "bold"),
        )
        header.pack(fill="x")
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

        def build_font_submenu_content(submenu_frame: tk.Misc) -> None:
            for font_name in self.FONT_CHOICES:
                self._create_radio_button(
                    submenu_frame, font_name, self.font_family, font_name, self._change_font_family
                ).pack(fill="x")

        self._create_submenu_button(
            popup, translate("info.menu.font"), "font_submenu", build_font_submenu_content
        ).pack(fill="x")

        tk.Frame(popup, height=1, bg=ACCENT).pack(fill="x", pady=2)
        colors = get_filter_colors()
        for message_id, command in (
            ("info.menu.refresh", self._auto_sync),
            ("info.menu.lock", self._toggle_lock),
            ("info.menu.close", self._close_overlay),
        ):
            label = translate(message_id)
            foreground = colors.matched if message_id == "info.menu.lock" and self.locked else TEXT
            button = tk.Button(
                popup,
                text=label,
                bg=CARD_BG,
                fg=foreground,
                bd=0,
                anchor="w",
                padx=10,
                pady=5,
                font=(self.font_family, self.font_size),
                activebackground=ACCENT,
                activeforeground=CARD_BG,
                command=lambda action=command, key=message_id: (
                    action(),
                    self._destroy_settings_popup(),
                    self._show_context_menu(event=None) if key != "info.menu.close" else None,
                ),
            )
            button.pack(fill="x")

        popup.geometry(f"+{self._last_menu_pos[0]}+{self._last_menu_pos[1]}")
        popup.bind("<FocusOut>", self._on_popup_focus_out)
        popup.bind("<Escape>", lambda _: (popup.destroy(), self._close_all_submenus()))
        popup.focus_set()
