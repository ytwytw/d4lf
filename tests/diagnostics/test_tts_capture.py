from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from src import tts
from src.diagnostics.tts_capture import AppTtsCaptureController, CaptureControllerError, CaptureState
from src.scripts import common

if TYPE_CHECKING:
    from pathlib import Path


def test_app_capture_start_record_stop_writes_cli_compatible_jsonl(tmp_path: Path) -> None:
    timestamps = iter([
        datetime(2026, 7, 10, 20, 30, 0, tzinfo=UTC),
        datetime(2026, 7, 10, 20, 30, 1, tzinfo=UTC),
        datetime(2026, 7, 10, 20, 30, 2, tzinfo=UTC),
    ])
    controller = AppTtsCaptureController(clock=lambda: next(timestamps), monotonic=lambda: 10.0)

    snapshot = controller.start(
        output_dir=tmp_path,
        locale="zhCN",
        game_build="3.1.0.72698",
        category="core",
        metadata={"area": "inventory", "capture_source": "desktop-app"},
    )
    assert snapshot.active
    assert controller.record_payload("先祖传奇双手剑\0".encode())
    assert controller.record_payload(b"Mouse Button 4\0")

    result = controller.stop()

    assert result.message_count == 2
    assert result.output_path.exists()
    records = [json.loads(line) for line in result.output_path.read_text(encoding="utf-8").splitlines()]
    assert [record["sequence"] for record in records] == [1, 2]
    assert [record["raw_text"] for record in records] == ["先祖传奇双手剑", "Mouse Button 4"]
    assert records[0]["locale"] == "zhCN"
    assert records[0]["game_build"] == "3.1.0.72698"
    assert records[0]["session"]["metadata"] == {
        "area": "inventory",
        "capture_source": "desktop-app",
        "category": "core",
    }
    assert controller.snapshot().state == CaptureState.SAVED
    assert not list(tmp_path.glob(".*.tmp"))


def test_app_capture_never_overwrites_an_existing_session(tmp_path: Path) -> None:
    fixed_time = datetime(2026, 7, 10, 20, 30, 0, tzinfo=UTC)
    controller = AppTtsCaptureController(clock=lambda: fixed_time)

    controller.start(output_dir=tmp_path, locale="zhCN", game_build="3.1.0.72698", category="core")
    first = controller.stop()
    controller.start(output_dir=tmp_path, locale="zhCN", game_build="3.1.0.72698", category="core")
    second = controller.stop()

    assert first.output_path != second.output_path
    assert first.output_path.exists()
    assert second.output_path.exists()
    assert second.output_path.stem.endswith("-2")


def test_app_capture_failure_is_contained_and_removes_temporary_output(tmp_path: Path) -> None:
    fixed_time = datetime(2026, 7, 10, 20, 30, 0, tzinfo=UTC)
    controller = AppTtsCaptureController(clock=lambda: fixed_time)
    snapshot = controller.start(output_dir=tmp_path, locale="zhCN", game_build="3.1.0.72698", category="core")

    assert not controller.record_payload(b"\xff")
    assert controller.snapshot().state == CaptureState.ERROR
    assert snapshot.output_path is not None
    assert not snapshot.output_path.exists()
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(CaptureControllerError, match="No diagnostic TTS capture is running"):
        controller.stop()


def test_app_capture_rejects_parallel_sessions(tmp_path: Path) -> None:
    fixed_time = datetime(2026, 7, 10, 20, 30, 0, tzinfo=UTC)
    controller = AppTtsCaptureController(clock=lambda: fixed_time)
    controller.start(output_dir=tmp_path, locale="zhCN", game_build="3.1.0.72698", category="core")

    with pytest.raises(CaptureControllerError, match="already running"):
        controller.start(output_dir=tmp_path, locale="zhCN", game_build="3.1.0.72698", category="core")

    controller.stop()


def test_diagnostic_capture_blocks_new_game_input(mocker) -> None:
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=True)

    assert not common.game_input_allowed("test action", language="enUS")


def test_live_tts_path_taps_the_raw_payload_before_runtime_normalization(mocker) -> None:
    record_payload = mocker.patch.object(tts.APP_TTS_CAPTURE, "record_payload")
    payload = "  中文\0".encode()

    decoded = tts.record_and_decode_pipe_payload(payload)

    record_payload.assert_called_once_with(payload)
    assert decoded == "  中文"
