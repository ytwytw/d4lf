"""Application-owned, cooperative cleanup of the game-facing script handlers."""

import logging
from threading import Event, Thread
from typing import TYPE_CHECKING

from src.automation import safe_exit
from src.diagnostics import begin_shutdown
from src.overlay import request_close
from src.paragon.overlay import request_close as request_close_paragon

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.app.handler import ScriptHandler

LOGGER = logging.getLogger(__name__)
# Covers a cancelled export's final render and atomic replace, including its 2 s lock retry.
EXIT_SAVE_TIMEOUT = 3.0
_EXIT_REQUESTED = Event()


def request_exit(
    handler: ScriptHandler, *, timeout: float = EXIT_SAVE_TIMEOUT, exit_process: Callable[[], None] = safe_exit
) -> None:
    """Exit hotkey: block game input now, give a running export a bounded final save, then hard-exit.

    Without an export, or on a second press while waiting, the process stops immediately as before.
    The wait runs off the keyboard-hook thread so that hook is never held up.
    """
    if _EXIT_REQUESTED.is_set() or not handler.inventory_dump_running:
        exit_process()
        return
    _EXIT_REQUESTED.set()
    handler._shutting_down = True
    handler.cancel_inventory_dump()
    begin_shutdown()

    def finish() -> None:
        try:
            if not handler.wait_for_inventory_dump(timeout):
                LOGGER.warning("Inventory export did not finish within %.1f s; exiting anyway", timeout)
        finally:
            exit_process()

    Thread(target=finish, name="exit-after-export-save", daemon=True).start()


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
