"""Public local-only diagnostic capture interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.diagnostics.safety import GameInputCancelledError, begin_shutdown

if TYPE_CHECKING:
    import numpy as np

    from src.diagnostics.auto_failure_capture import AutoFailureCaptureResult


def allow_game_input(action: str) -> bool:
    from src.diagnostics.safety import allow_game_input as implementation  # ruff:ignore[import-outside-top-level]

    return implementation(action)


def capture_latest_failure(
    *, reason: str, image: np.ndarray, error: BaseException | str | None = None
) -> AutoFailureCaptureResult | None:
    from src.diagnostics.auto_failure_capture import capture_latest_failure as implementation  # ruff:ignore[import-outside-top-level]

    return implementation(reason=reason, image=image, error=error)


def game_input_blocked() -> bool:
    from src.diagnostics.safety import game_input_blocked as implementation  # ruff:ignore[import-outside-top-level]

    return implementation()


def is_diagnostic_capture_active() -> bool:
    from src.diagnostics.tts_capture import is_diagnostic_capture_active as implementation  # ruff:ignore[import-outside-top-level]

    return implementation()


def record_raw_tts(text: str) -> bool:
    from src.diagnostics.tts_capture import record_raw_tts as implementation  # ruff:ignore[import-outside-top-level]

    return implementation(text)


__all__ = [
    "GameInputCancelledError",
    "allow_game_input",
    "begin_shutdown",
    "capture_latest_failure",
    "game_input_blocked",
    "is_diagnostic_capture_active",
    "record_raw_tts",
]
