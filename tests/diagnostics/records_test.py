import json
from datetime import UTC, datetime
from typing import cast

import pytest

from src.diagnostics.records import AtomicJsonlWriter, CaptureSession, capture_record, utc_timestamp


def test_capture_record_preserves_unicode_and_session_metadata() -> None:
    timestamp = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    session = CaptureSession(started_at=utc_timestamp(timestamp), metadata={"category": "manual"})

    record = capture_record(
        text="先祖传奇双手剑", locale="zhCN", game_build="2.4.0", session=session, sequence=1, captured_at=timestamp
    )

    assert record["raw_text"] == "先祖传奇双手剑"
    assert record["locale"] == "zhCN"
    session_record = record["session"]
    assert isinstance(session_record, dict)
    assert cast("dict[str, object]", session_record)["metadata"] == {"category": "manual"}


def test_atomic_jsonl_writer_commits_complete_records(tmp_path) -> None:
    destination = tmp_path / "capture.jsonl"
    writer = AtomicJsonlWriter(destination)
    writer.open()
    writer.write({"raw_text": "中文"})
    writer.commit()

    assert json.loads(destination.read_text(encoding="utf-8")) == {"raw_text": "中文"}
    assert not list(tmp_path.glob("*.tmp"))


def test_utc_timestamp_rejects_naive_values() -> None:
    naive = datetime.now(UTC).replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_timestamp(naive)
