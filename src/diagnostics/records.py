"""Atomic JSONL records shared by manual and automatic TTS captures."""

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = "Capture timestamps must be timezone-aware."
        raise ValueError(msg)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class CaptureSession:
    started_at: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def as_json(self) -> dict[str, object]:
        return {"id": self.session_id, "started_at": self.started_at, "metadata": dict(self.metadata)}


def capture_record(
    *, text: str, locale: str, game_build: str, session: CaptureSession, sequence: int, captured_at: datetime
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "locale": locale,
        "game_build": game_build,
        "session": session.as_json(),
        "sequence": sequence,
        "timestamp": utc_timestamp(captured_at),
        "raw_text": text,
    }


class AtomicJsonlWriter:
    """Write a capture to a sibling temporary file and publish it atomically."""

    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self._fd: int | None = None
        self._temporary_path: Path | None = None

    def open(self) -> None:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self._fd, temporary_name = tempfile.mkstemp(
            dir=self.destination.parent, prefix=f".{self.destination.name}.", suffix=".tmp"
        )
        self._temporary_path = Path(temporary_name)

    def write(self, record: Mapping[str, object]) -> None:
        if self._fd is None:
            msg = "The JSONL writer is not open."
            raise RuntimeError(msg)
        payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        remaining = memoryview((payload + "\n").encode("utf-8"))
        while remaining:
            written = os.write(self._fd, remaining)
            if written == 0:
                msg = "Could not write the JSONL record."
                raise OSError(msg)
            remaining = remaining[written:]

    def commit(self) -> None:
        if self._fd is None or self._temporary_path is None:
            msg = "The JSONL writer is not open."
            raise RuntimeError(msg)
        os.fsync(self._fd)
        os.close(self._fd)
        self._fd = None
        self._temporary_path.replace(self.destination)
        self._temporary_path = None

    def abort(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        if self._temporary_path is not None:
            self._temporary_path.unlink(missing_ok=True)
            self._temporary_path = None


__all__ = ["AtomicJsonlWriter", "CaptureSession", "capture_record", "utc_now", "utc_timestamp"]
