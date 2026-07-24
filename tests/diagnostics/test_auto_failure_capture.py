import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import cv2
import numpy as np

from src.diagnostics.auto_failure_capture import AutoFailureCapture
from src.tools.tts_replay import load_capture

if TYPE_CHECKING:
    from pathlib import Path


def test_automatic_failure_capture_is_disabled_without_writing(tmp_path: Path) -> None:
    capture = AutoFailureCapture(capture_root=tmp_path, enabled=False)

    result = capture.capture(
        reason="test-failure",
        image=np.zeros((20, 30, 3), dtype=np.uint8),
        tts_lines=["Item", "Legendary Helm"],
        locale="zhCN",
        game_build="3.1.0.72810",
    )

    assert result is None
    assert not list(tmp_path.iterdir())


def test_automatic_failure_capture_does_not_propagate_storage_errors(tmp_path: Path) -> None:
    unavailable_root = tmp_path / "not-a-directory"
    unavailable_root.write_text("occupied", encoding="utf-8")
    capture = AutoFailureCapture(capture_root=unavailable_root, enabled=True)

    result = capture.capture(
        reason="test-failure",
        image=np.zeros((20, 30, 3), dtype=np.uint8),
        tts_lines=["Item", "Legendary Helm"],
        locale="zhCN",
        game_build="3.1.0.72810",
    )

    assert result is None
    assert unavailable_root.read_text(encoding="utf-8") == "occupied"


def test_automatic_failure_capture_writes_paired_replayable_bundle_and_deduplicates(tmp_path: Path) -> None:
    start = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    timestamps = iter([start, start + timedelta(seconds=10), start + timedelta(seconds=20)])
    capture = AutoFailureCapture(capture_root=tmp_path, enabled=True, clock=lambda: next(timestamps))
    image = np.full((20, 30, 3), 127, dtype=np.uint8)
    detail_image = np.full((10, 15, 3), 64, dtype=np.uint8)
    framed_lines = ["Item", "Legendary Helm", "Mouse Right Button"]
    raw_lines = ["[FAVORITED ITEM]. Item", "Legendary Helm", "Mouse Right Button"]

    result = capture.capture(
        reason="tts-item-parse-failed",
        image=image,
        detail_image=detail_image,
        tts_lines=framed_lines,
        raw_tts_lines=raw_lines,
        error=ValueError("unrecognized affix"),
        locale="zhCN",
        game_build="3.1.0.72810",
    )
    duplicate = capture.capture(
        reason="tts-item-parse-failed",
        image=image,
        tts_lines=framed_lines,
        raw_tts_lines=raw_lines,
        locale="zhCN",
        game_build="3.1.0.72810",
    )
    distinct_failure = capture.capture(
        reason="visual-item-parse-failed",
        image=image,
        tts_lines=framed_lines,
        raw_tts_lines=raw_lines,
        locale="zhCN",
        game_build="3.1.0.72810",
    )

    assert result is not None
    assert duplicate is None
    assert distinct_failure is not None
    assert sorted(path.name for path in result.bundle_dir.iterdir()) == [
        "manifest.json",
        "screenshot.png",
        "tooltip.png",
        "tts.jsonl",
    ]
    screenshot = cv2.imread(str(result.bundle_dir / "screenshot.png"))
    tooltip = cv2.imread(str(result.bundle_dir / "tooltip.png"))
    assert screenshot is not None
    assert tooltip is not None
    assert screenshot.shape == image.shape
    assert tooltip.shape == detail_image.shape
    replay = load_capture(result.bundle_dir / "tts.jsonl")
    assert replay.locale == "zhCN"
    assert replay.game_build == "3.1.0.72810"
    assert [record.raw_text for record in replay.records] == raw_lines
    manifest = json.loads((result.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["reason"] == "tts-item-parse-failed"
    assert manifest["detail_image"] == {"file": "tooltip.png", "height": 10, "width": 15}
    assert manifest["tts"]["framed_lines"] == framed_lines
    assert manifest["tts"]["raw_lines"] == raw_lines
    assert manifest["error"] == {"type": "ValueError", "message": "unrecognized affix"}
    assert len(list(tmp_path.glob("failure-*"))) == 2


def test_automatic_failure_capture_limits_retained_bundles(tmp_path: Path) -> None:
    start = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    timestamps = iter(start + timedelta(seconds=index) for index in range(3))
    capture = AutoFailureCapture(
        capture_root=tmp_path, enabled=True, clock=lambda: next(timestamps), max_bundles=2, dedupe_seconds=0
    )
    image = np.zeros((10, 10, 3), dtype=np.uint8)

    results = [
        capture.capture(
            reason="test-failure", image=image, tts_lines=[f"Item {index}"], locale="enUS", game_build="3.1.0.72810"
        )
        for index in range(3)
    ]

    assert all(result is not None for result in results)
    first_result = results[0]
    assert first_result is not None
    assert not first_result.bundle_dir.exists()
    assert len(list(tmp_path.glob("failure-*"))) == 2
