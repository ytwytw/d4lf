from datetime import UTC, datetime

import pytest

from src.diagnostics.tts_capture import AppTtsCaptureController, CaptureControllerError, CaptureState


def test_manual_capture_records_raw_text_and_stops_atomically(tmp_path) -> None:
    capture = AppTtsCaptureController(clock=lambda: datetime(2026, 7, 26, 12, 0, tzinfo=UTC))

    started = capture.start(output_dir=tmp_path, locale="zhCN", game_build="2.4.0")
    assert started.state is CaptureState.RECORDING
    assert capture.record_text("先祖传奇双手剑")
    result = capture.stop()

    assert result.message_count == 1
    assert '"raw_text":"先祖传奇双手剑"' in result.output_path.read_text(encoding="utf-8")
    assert capture.snapshot().state is CaptureState.SAVED


def test_manual_capture_rejects_parallel_sessions(tmp_path) -> None:
    capture = AppTtsCaptureController()
    capture.start(output_dir=tmp_path, locale="zhCN", game_build="unknown")

    with pytest.raises(CaptureControllerError, match="already running"):
        capture.start(output_dir=tmp_path, locale="zhCN", game_build="unknown")


def test_idle_capture_does_not_create_files(tmp_path) -> None:
    capture = AppTtsCaptureController()

    assert capture.record_text("ignored") is False
    assert list(tmp_path.iterdir()) == []
