"""Lowest-level safety gate for manual diagnostic recording."""

import logging

from src.diagnostics.tts_capture import is_diagnostic_capture_active

LOGGER = logging.getLogger(__name__)


def game_input_blocked() -> bool:
    """Return True only while an explicit manual capture is recording."""
    return is_diagnostic_capture_active()


def allow_game_input(action: str) -> bool:
    if not game_input_blocked():
        return True
    LOGGER.warning("Skipping %s while manual diagnostic capture is active", action)
    return False


__all__ = ["allow_game_input", "game_input_blocked"]
