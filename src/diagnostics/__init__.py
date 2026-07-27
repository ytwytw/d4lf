"""Public local-only diagnostic capture interface."""


def allow_game_input(action: str) -> bool:
    from src.diagnostics.safety import allow_game_input as implementation  # ruff:ignore[import-outside-top-level]

    return implementation(action)


def capture_latest_failure(**kwargs):
    from src.diagnostics.auto_failure_capture import (  # ruff:ignore[import-outside-top-level]
        capture_latest_failure as implementation,
    )

    return implementation(**kwargs)


def game_input_blocked() -> bool:
    from src.diagnostics.safety import game_input_blocked as implementation  # ruff:ignore[import-outside-top-level]

    return implementation()


def is_diagnostic_capture_active() -> bool:
    from src.diagnostics.tts_capture import (  # ruff:ignore[import-outside-top-level]
        is_diagnostic_capture_active as implementation,
    )

    return implementation()


def record_raw_tts(text: str) -> bool:
    from src.diagnostics.tts_capture import record_raw_tts as implementation  # ruff:ignore[import-outside-top-level]

    return implementation(text)


__all__ = ["allow_game_input", "capture_latest_failure", "game_input_blocked", "is_diagnostic_capture_active", "record_raw_tts"]
