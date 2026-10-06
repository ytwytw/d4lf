"""Lowest-level safety gate for manual diagnostic recording."""

import logging
from threading import Event

from src.diagnostics.tts_capture import is_diagnostic_capture_active

LOGGER = logging.getLogger(__name__)
_SHUTDOWN_REQUESTED = Event()


class GameInputCancelledError(Exception):
    """Cooperative cancellation at an automation input boundary during shutdown."""


def begin_shutdown() -> None:
    """Permanently prevent new game input from this process during teardown."""
    _SHUTDOWN_REQUESTED.set()


def game_input_blocked() -> bool:
    """Return whether manual capture or application teardown blocks game input."""
    return _SHUTDOWN_REQUESTED.is_set() or is_diagnostic_capture_active()


def allow_game_input(action: str) -> bool:
    if _SHUTDOWN_REQUESTED.is_set():
        raise GameInputCancelledError
    if not game_input_blocked():
        return True
    LOGGER.warning("Skipping %s while manual diagnostic capture is active", action)
    return False


__all__ = ["GameInputCancelledError", "allow_game_input", "begin_shutdown", "game_input_blocked"]
