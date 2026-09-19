"""Application hotkey settings that determine the active runtime bindings."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
