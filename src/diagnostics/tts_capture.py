"""In-app raw TTS capture controller."""

import enum
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.diagnostics.records import AtomicJsonlWriter, CaptureSession, capture_record, utc_now, utc_timestamp

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path


class CaptureState(enum.StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    SAVED = "saved"
    ERROR = "error"


class CaptureControllerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CaptureSnapshot:
    state: CaptureState
    message_count: int
    output_path: Path | None
    elapsed_seconds: float
    error: str | None

    @property
    def active(self) -> bool:
        return self.state is CaptureState.RECORDING


@dataclass(frozen=True, slots=True)
class CaptureResult:
    output_path: Path
    message_count: int
    locale: str
    game_build: str


class AppTtsCaptureController:
    def __init__(
        self, *, clock: Callable[[], datetime] = utc_now, monotonic: Callable[[], float] = time.monotonic
    ) -> None:
        self._clock = clock
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._state = CaptureState.IDLE
        self._writer: AtomicJsonlWriter | None = None
        self._session: CaptureSession | None = None
        self._output_path: Path | None = None
        self._locale = ""
        self._game_build = ""
        self._started_monotonic: float | None = None
        self._message_count = 0
        self._error: str | None = None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._state is CaptureState.RECORDING

    def start(
        self, *, output_dir: Path, locale: str, game_build: str, metadata: Mapping[str, str] | None = None
    ) -> CaptureSnapshot:
        with self._lock:
            if self._state is CaptureState.RECORDING:
                message = "A diagnostic TTS capture is already running."
                raise CaptureControllerError(message)
            started = self._clock()
            self._locale = locale.strip() or "unknown"
            self._game_build = game_build.strip() or "unknown"
            timestamp = started.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            stem = "-".join(self._file_part(value) for value in (self._locale, self._game_build, timestamp))
            self._output_path = self._unique_path(output_dir / f"{stem}.jsonl")
            self._session = CaptureSession(
                started_at=utc_timestamp(started),
                metadata={"category": "manual", "capture_source": "desktop-app", **dict(metadata or {})},
            )
            self._writer = AtomicJsonlWriter(self._output_path)
            try:
                self._writer.open()
            except OSError as error:
                self._state = CaptureState.ERROR
                self._error = str(error)
                message = f"Could not start diagnostic capture: {error}"
                raise CaptureControllerError(message) from error
            self._message_count = 0
            self._error = None
            self._started_monotonic = self._monotonic()
            self._state = CaptureState.RECORDING
            return self._snapshot_locked()

    def record_text(self, text: str) -> bool:
        with self._lock:
            if self._state is not CaptureState.RECORDING:
                return False
            if self._writer is None or self._session is None:
                self._fail_locked("Diagnostic capture entered an invalid state.")
                return False
            sequence = self._message_count + 1
            try:
                self._writer.write(
                    capture_record(
                        text=text,
                        locale=self._locale,
                        game_build=self._game_build,
                        session=self._session,
                        sequence=sequence,
                        captured_at=self._clock(),
                    )
                )
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                self._fail_locked(str(error))
                return False
            self._message_count = sequence
            return True

    def stop(self) -> CaptureResult:
        with self._lock:
            if self._state is not CaptureState.RECORDING or self._writer is None or self._output_path is None:
                message = "No diagnostic TTS capture is running."
                raise CaptureControllerError(message)
            try:
                self._writer.commit()
            except (OSError, RuntimeError) as error:
                self._fail_locked(str(error))
                message = f"Could not save diagnostic capture: {error}"
                raise CaptureControllerError(message) from error
            result = CaptureResult(self._output_path, self._message_count, self._locale, self._game_build)
            self._writer = None
            self._session = None
            self._started_monotonic = None
            self._state = CaptureState.SAVED
            return result

    def snapshot(self) -> CaptureSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> CaptureSnapshot:
        elapsed = (
            max(0.0, self._monotonic() - self._started_monotonic)
            if self._state is CaptureState.RECORDING and self._started_monotonic is not None
            else 0.0
        )
        return CaptureSnapshot(self._state, self._message_count, self._output_path, elapsed, self._error)

    def _fail_locked(self, message: str) -> None:
        if self._writer is not None:
            self._writer.abort()
        self._writer = None
        self._session = None
        self._started_monotonic = None
        self._state = CaptureState.ERROR
        self._error = message

    @staticmethod
    def _file_part(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "capture"

    @staticmethod
    def _unique_path(path: Path) -> Path:
        candidate, suffix = path, 2
        while candidate.exists():
            candidate = path.with_stem(f"{path.stem}-{suffix}")
            suffix += 1
        return candidate


APP_TTS_CAPTURE = AppTtsCaptureController()


def record_raw_tts(text: str) -> bool:
    return APP_TTS_CAPTURE.record_text(text)


def is_diagnostic_capture_active() -> bool:
    return APP_TTS_CAPTURE.is_active


__all__ = [
    "APP_TTS_CAPTURE",
    "AppTtsCaptureController",
    "CaptureControllerError",
    "CaptureResult",
    "CaptureSnapshot",
    "CaptureState",
    "is_diagnostic_capture_active",
    "record_raw_tts",
]
