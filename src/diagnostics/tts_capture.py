from __future__ import annotations

import enum
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.tools.tts_capture import AtomicJsonlWriter, CaptureSession, build_capture_record, utc_now, utc_timestamp

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

LOGGER = logging.getLogger(__name__)


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
    locale: str | None
    game_build: str | None
    started_at: str | None
    elapsed_seconds: float
    error: str | None

    @property
    def active(self) -> bool:
        return self.state == CaptureState.RECORDING


@dataclass(frozen=True, slots=True)
class CaptureResult:
    output_path: Path
    message_count: int
    locale: str
    game_build: str
    started_at: str


class AppTtsCaptureController:
    """Thread-safe raw TTS recorder controlled by the desktop application."""

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
        self._locale: str | None = None
        self._game_build: str | None = None
        self._started_monotonic: float | None = None
        self._message_count = 0
        self._error: str | None = None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._state == CaptureState.RECORDING

    def start(
        self,
        *,
        output_dir: Path,
        locale: str,
        game_build: str,
        category: str,
        metadata: Mapping[str, str] | None = None,
    ) -> CaptureSnapshot:
        locale = self._required_value(locale, "locale")
        game_build = self._required_value(game_build, "game_build")
        category = self._required_value(category, "category")

        with self._lock:
            if self._state == CaptureState.RECORDING:
                message = "A diagnostic TTS capture is already running."
                raise CaptureControllerError(message)

            started = self._clock()
            started_at = utc_timestamp(started)
            output_path = self._unique_output_path(
                output_dir=output_dir, locale=locale, game_build=game_build, category=category, started=started
            )
            session_metadata = dict(metadata or {})
            session_metadata["category"] = category
            session = CaptureSession(session_id=str(uuid.uuid4()), started_at=started_at, metadata=session_metadata)
            writer = AtomicJsonlWriter(output_path)
            try:
                writer.open()
            except OSError as error:
                self._state = CaptureState.ERROR
                self._error = str(error)
                message = f"Could not start diagnostic capture: {error}"
                raise CaptureControllerError(message) from error

            self._writer = writer
            self._session = session
            self._output_path = output_path
            self._locale = locale
            self._game_build = game_build
            self._started_monotonic = self._monotonic()
            self._message_count = 0
            self._error = None
            self._state = CaptureState.RECORDING
            return self._snapshot_locked()

    def record_payload(self, payload: bytes) -> bool:
        with self._lock:
            if self._state != CaptureState.RECORDING:
                return False
            if self._writer is None or self._session is None or self._locale is None or self._game_build is None:
                self._fail_locked("Diagnostic capture entered an invalid internal state.")
                return False

            sequence = self._message_count + 1
            try:
                record = build_capture_record(
                    payload=payload,
                    locale=self._locale,
                    game_build=self._game_build,
                    session=self._session,
                    sequence=sequence,
                    captured_at=self._clock(),
                )
                self._writer.write(record)
            except (OSError, RuntimeError, TypeError, UnicodeError, ValueError) as error:
                LOGGER.error("Diagnostic TTS capture stopped after a write failure: %s", error)
                self._fail_locked(str(error))
                return False

            self._message_count = sequence
            return True

    def stop(self) -> CaptureResult:
        with self._lock:
            if self._state != CaptureState.RECORDING:
                message = "No diagnostic TTS capture is running."
                raise CaptureControllerError(message)
            if (
                self._writer is None
                or self._session is None
                or self._output_path is None
                or self._locale is None
                or self._game_build is None
            ):
                self._fail_locked("Diagnostic capture entered an invalid internal state.")
                raise CaptureControllerError(self._error or "Diagnostic capture failed.")

            try:
                self._writer.commit()
            except OSError as error:
                self._fail_locked(str(error))
                message = f"Could not save diagnostic capture: {error}"
                raise CaptureControllerError(message) from error

            result = CaptureResult(
                output_path=self._output_path,
                message_count=self._message_count,
                locale=self._locale,
                game_build=self._game_build,
                started_at=self._session.started_at,
            )
            self._writer = None
            self._session = None
            self._started_monotonic = None
            self._state = CaptureState.SAVED
            return result

    def snapshot(self) -> CaptureSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> CaptureSnapshot:
        elapsed = 0.0
        if self._state == CaptureState.RECORDING and self._started_monotonic is not None:
            elapsed = max(0.0, self._monotonic() - self._started_monotonic)
        return CaptureSnapshot(
            state=self._state,
            message_count=self._message_count,
            output_path=self._output_path,
            locale=self._locale,
            game_build=self._game_build,
            started_at=self._session.started_at if self._session is not None else None,
            elapsed_seconds=elapsed,
            error=self._error,
        )

    def _fail_locked(self, message: str) -> None:
        if self._writer is not None:
            try:
                self._writer.abort()
            except OSError as cleanup_error:
                LOGGER.error("Could not remove a failed diagnostic capture temporary file: %s", cleanup_error)
        self._writer = None
        self._session = None
        self._started_monotonic = None
        self._state = CaptureState.ERROR
        self._error = message

    @classmethod
    def _unique_output_path(
        cls, *, output_dir: Path, locale: str, game_build: str, category: str, started: datetime
    ) -> Path:
        timestamp = started.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        stem = "-".join(cls._filename_component(value) for value in (locale, game_build, category, timestamp))
        candidate = output_dir / f"{stem}.jsonl"
        suffix = 2
        while candidate.exists():
            candidate = output_dir / f"{stem}-{suffix}.jsonl"
            suffix += 1
        return candidate

    @staticmethod
    def _filename_component(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
        return cleaned or "capture"

    @staticmethod
    def _required_value(value: str, label: str) -> str:
        value = value.strip()
        if not value:
            message = f"{label} must not be empty."
            raise CaptureControllerError(message)
        return value


APP_TTS_CAPTURE = AppTtsCaptureController()


def is_diagnostic_capture_active() -> bool:
    return APP_TTS_CAPTURE.is_active
