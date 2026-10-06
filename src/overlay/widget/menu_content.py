"""Information-overlay submenu content."""

import tkinter as tk
from typing import TYPE_CHECKING

from src.localization import translate
from src.overlay.settings import setting_int as _setting_int
from src.overlay.widget.shared import ACCENT, ACTIVE_GREEN, CARD_BG, MUTED, TEXT, OverlayContract

if TYPE_CHECKING:
    from collections.abc import Callable


class _OverlayMenuContent(OverlayContract):
    def _build_gold_submenu_content(self, submenu_frame: tk.Misc) -> None:
        def update_dependent_widgets() -> None:
            is_tracking = bool(self.capture_gold_stats)
            show_gph = bool(self.show_gph)
            show_total_gold = bool(self.show_total_gold)
            state = tk.NORMAL if is_tracking else tk.DISABLED
            btn_gph.config(state=state, fg=ACTIVE_GREEN if is_tracking and show_gph else MUTED)
            btn_gained.config(state=state, fg=ACTIVE_GREEN if is_tracking and show_total_gold else MUTED)

        self._create_toggle_btn(
            submenu_frame, translate("info.menu.gold.track"), "capture_gold_stats", callback=update_dependent_widgets
        )
        tk.Frame(submenu_frame, height=1, bg=ACCENT).pack(fill="x", pady=2)
        btn_gph = self._create_toggle_btn(submenu_frame, translate("info.menu.gold.show_per_hour"), "show_gph")
        btn_gained = self._create_toggle_btn(submenu_frame, translate("info.menu.gold.show_gained"), "show_total_gold")
        update_dependent_widgets()

    def _build_exp_submenu_content(self, submenu_frame: tk.Misc) -> None:
        def update_dependent_widgets() -> None:
            is_tracking = bool(self.capture_exp_stats)
            state = tk.NORMAL if is_tracking else tk.DISABLED
            for button, enabled in (
                (btn_eph, self.show_eph),
                (btn_gained, self.show_total_exp),
                (btn_t2l, self.show_t2l),
                (btn_next, self.show_next_scan),
                (btn_inv, self.settings.get("check_exp_on_inventory_open")),
            ):
                button.config(state=state, fg=ACTIVE_GREEN if is_tracking and bool(enabled) else MUTED)
            for button in (btn_age, btn_pick, btn_reset_pos):
                button.config(state=state, fg=TEXT if is_tracking else MUTED)
            if self.settings.get("exp_bar_pos") is None:
                btn_reset_pos.pack_forget()
            else:
                btn_reset_pos.pack(fill="x")

        self._create_toggle_btn(
            submenu_frame, translate("info.menu.exp.track"), "capture_exp_stats", callback=update_dependent_widgets
        )
        tk.Frame(submenu_frame, height=1, bg=ACCENT).pack(fill="x", pady=2)
        btn_eph = self._create_toggle_btn(submenu_frame, translate("info.menu.exp.show_per_hour"), "show_eph")
        btn_gained = self._create_toggle_btn(submenu_frame, translate("info.menu.exp.show_gained"), "show_total_exp")
        btn_t2l = self._create_toggle_btn(submenu_frame, translate("info.menu.exp.show_time_to_level"), "show_t2l")
        btn_next = self._create_toggle_btn(submenu_frame, translate("info.menu.exp.show_next_scan"), "show_next_scan")
        tk.Frame(submenu_frame, height=1, bg=ACCENT).pack(fill="x", pady=2)
        btn_inv = self._create_config_toggle_btn(
            submenu_frame, translate("info.menu.exp.auto_capture"), "check_exp_on_inventory_open"
        )
        btn_age = self._create_submenu_button(
            submenu_frame,
            translate("info.menu.exp.capture_time"),
            "exp_age_sub_submenu",
            self._build_exp_age_submenu_content,
        )
        tk.Frame(submenu_frame, height=1, bg=ACCENT).pack(fill="x", pady=2)
        btn_pick = self._submenu_action_button(submenu_frame, "info.menu.exp.configure_bar", self._pick_exp_bar_pos)
        btn_reset_pos = self._submenu_action_button(submenu_frame, "info.menu.exp.reset_bar", self._reset_exp_bar_pos)
        update_dependent_widgets()

    def _build_exp_age_submenu_content(self, submenu_frame: tk.Misc) -> None:
        options = [(-1, translate("info.state.never"))]
        options.extend(
            (minutes, translate("info.duration.minutes", minutes=minutes)) for minutes in (0, 3, 5, 10, 30, 60)
        )
        for value, label in options:
            self._create_radio_button(
                submenu_frame,
                label,
                _setting_int(self.settings, "exp_age_before_refresh", 5),
                value,
                lambda _: None,
                config_key="exp_age_before_refresh",
            ).pack(fill="x")

    def _submenu_action_button(
        self, submenu_frame: tk.Misc, message_id: str, command: Callable[[], object]
    ) -> tk.Button:
        button = tk.Button(
            submenu_frame,
            text=translate(message_id),
            bg=CARD_BG,
            fg=TEXT,
            bd=0,
            anchor="w",
            padx=10,
            pady=5,
            font=(self.font_family, self.font_size, "bold"),
            activebackground=ACCENT,
            activeforeground=CARD_BG,
            command=lambda: (command(), self._destroy_settings_popup(), self._close_all_submenus()),
        )
        button.pack(fill="x")
        return button

    def _build_reset_submenu_content(self, submenu_frame: tk.Misc) -> None:
        for message_id, command in (
            ("info.menu.reset_gold", self._reset_gold_stats),
            ("info.menu.reset_exp", self._reset_exp_stats),
        ):
            tk.Button(
                submenu_frame,
                text=translate(message_id),
                bg=CARD_BG,
                fg=TEXT,
                bd=0,
                anchor="w",
                padx=10,
                pady=5,
                font=(self.font_family, self.font_size, "bold"),
                activebackground=ACCENT,
                activeforeground=CARD_BG,
                command=command,
            ).pack(fill="x")
