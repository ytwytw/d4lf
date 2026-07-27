import src.diagnostics as diagnostics


def test_diagnostics_facade_exposes_capture_and_safety_capabilities() -> None:
    assert callable(diagnostics.capture_latest_failure)
    assert callable(diagnostics.record_raw_tts)
    assert callable(diagnostics.allow_game_input)
