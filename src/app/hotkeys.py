"""Application hotkey settings that determine the active runtime bindings."""

from typing import TYPE_CHECKING

from src import automation
from src.app.interaction import GAME_INTERACTION_LOCK
from src.app.shutdown import request_exit
from src.automation import is_window_foreground
from src.overlay import InventoryExpTracker
from src.settings import ItemRefreshType

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.app.handler import ScriptHandler
    from src.settings import Settings


def hotkey_signature(config: Settings) -> tuple[str | bool, ...]:
    advanced_options = config.advanced_options
    return (
        advanced_options.run_vision_mode,
        advanced_options.exit_key,
        advanced_options.info_overlay,
        advanced_options.toggle_paragon_overlay,
        advanced_options.vision_mode_only,
        advanced_options.run_filter,
        advanced_options.run_filter_drop,
        advanced_options.run_filter_force_refresh,
        advanced_options.force_refresh_only,
        advanced_options.move_to_inv,
        advanced_options.move_to_chest,
        config.char.inventory,
    )


class RuntimeHotkeys:
    def _register_hotkey(
        self: ScriptHandler, hotkey: str, callback: Callable[[], None], check_focus: bool = True
    ) -> None:
        def wrapped_callback() -> None:
            with GAME_INTERACTION_LOCK:
                if self._shutting_down or (check_focus and self.inventory_dump_running):
                    return
                if not check_focus or is_window_foreground(self._win_spec):
                    callback()

        self._hotkey_handles.append(automation.add_hotkey(hotkey, wrapped_callback))

    def setup_key_binds(self: ScriptHandler) -> None:
        config = self._config
        advanced_options = config.advanced_options
        self._register_hotkey(advanced_options.run_vision_mode, self.run_vision_mode)
        # Emergency stop must not wait for the interaction lock or block the keyboard hook.
        self._hotkey_handles.append(automation.add_hotkey(advanced_options.exit_key, lambda: request_exit(self)))
        self._register_hotkey(advanced_options.toggle_paragon_overlay, self.toggle_paragon_overlay)
        self._register_hotkey(advanced_options.info_overlay, self.toggle_info_overlay)
        self._register_hotkey(config.char.inventory, lambda: InventoryExpTracker().on_inventory_open())
        if not advanced_options.vision_mode_only:
            self._register_hotkey(advanced_options.run_filter, self.filter_items)
            self._register_hotkey(advanced_options.run_filter_drop, lambda: self.filter_items(no_match_action="drop"))
            self._register_hotkey(
                advanced_options.run_filter_force_refresh, lambda: self.filter_items(ItemRefreshType.force_with_filter)
            )
            self._register_hotkey(
                advanced_options.force_refresh_only, lambda: self.filter_items(ItemRefreshType.force_without_filter)
            )
            self._register_hotkey(advanced_options.move_to_inv, self.move_items_to_inventory)
            self._register_hotkey(advanced_options.move_to_chest, self.move_items_to_stash)
        self._current_hotkey_signature = hotkey_signature(config)
