import json
from datetime import UTC, datetime, timedelta

import numpy as np

from src.diagnostics.auto_failure_capture import AutoFailureCapture


def _image() -> np.ndarray:
    return np.zeros((8, 12, 3), dtype=np.uint8)


def test_automatic_failure_capture_is_disabled_without_writing(tmp_path) -> None:
    capture = AutoFailureCapture(capture_root=tmp_path, enabled=False)

    assert capture.capture(reason="parse", image=_image(), tts_lines=["item"]) is None
    assert list(tmp_path.iterdir()) == []


def test_automatic_failure_capture_writes_a_local_replayable_bundle_and_deduplicates(tmp_path) -> None:
    timestamps = iter([
        datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
        datetime(2026, 7, 26, 12, 1, tzinfo=UTC),
        datetime(2026, 7, 26, 12, 6, tzinfo=UTC),
    ])
    capture = AutoFailureCapture(capture_root=tmp_path, enabled=True, clock=lambda: next(timestamps))

    result = capture.capture(
        reason="item-parse",
        image=_image(),
        tts_lines=["传奇双手剑"],
        raw_tts_lines=["传奇", "双手剑"],
        locale="zhCN",
        game_build="2.4.0",
    )
    duplicate = capture.capture(
        reason="item-parse", image=_image(), tts_lines=["传奇双手剑"], locale="zhCN", game_build="2.4.0"
    )

    assert result is not None
    assert duplicate is None
    assert {path.name for path in result.bundle_dir.iterdir()} == {"manifest.json", "screenshot.png", "tts.jsonl"}
    manifest = json.loads((result.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["locale"] == "zhCN"
    assert manifest["tts"]["raw_lines"] == ["传奇", "双手剑"]
    assert '"raw_text":"传奇"' in (result.bundle_dir / "tts.jsonl").read_text(encoding="utf-8")


def test_automatic_failure_capture_retention_is_bounded(tmp_path) -> None:
    start = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    timestamps = iter(start + timedelta(seconds=index) for index in range(3))
    capture = AutoFailureCapture(
        capture_root=tmp_path, enabled=True, clock=lambda: next(timestamps), max_bundles=2, dedupe_seconds=0
    )

    for index in range(3):
        capture.capture(reason=f"failure-{index}", image=_image(), tts_lines=[str(index)])

    assert len([path for path in tmp_path.iterdir() if path.is_dir()]) == 2
