"""Application-owned, cooperative cleanup of the game-facing script handlers."""

import logging
from typing import TYPE_CHECKING

from src.diagnostics import begin_shutdown
from src.overlay import request_close
from src.paragon.overlay import request_close as request_close_paragon

if TYPE_CHECKING:
    from src.app.handler import ScriptHandler

LOGGER = logging.getLogger(__name__)


def shutdown_scripts(handler: ScriptHandler) -> None:
    """Stop callbacks before closing UI; never asynchronously terminate a worker."""
    begin_shutdown()
    with handler._runtime_config_lock:
        handler._shutting_down = True
        handler._config.unregister_change_listener(handler._on_config_changed)
        handler._clear_key_binds()
    handler.cancel_inventory_dump()
    handler.wait_for_inventory_dump()
    for cleanup in (handler.vision_mode.stop, request_close_paragon, request_close):
        try:
            cleanup()
        except Exception:
            LOGGER.exception("Script cleanup failed")
    for thread in (handler.loot_interaction_thread, handler.paragon_overlay_thread):
        if thread is not None:
            thread.join(timeout=2)
            if thread.is_alive():
                LOGGER.warning("Worker %s is still finishing; all new game input is blocked", thread.name)
