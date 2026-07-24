from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import cv2

from src import __version__
from src.config.loader import IniConfigLoader
from src.tools.tts_capture import CaptureSession, build_capture_record, utc_now, utc_timestamp

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    import numpy as np

LOGGER = logging.getLogger(__name__)
AUTO_CAPTURE_SCHEMA_VERSION = 2
DEFAULT_MAX_BUNDLES = 50
DEFAULT_DEDUPE_SECONDS = 300
UNKNOWN_GAME_BUILD = "unknown"
_BUNDLE_FILES = ("manifest.json", "screenshot.png", "tooltip.png", "tts.jsonl")
_DETECTED_GAME_BUILD = UNKNOWN_GAME_BUILD


@dataclass(frozen=True, slots=True)
class AutoFailureCaptureResult:
    bundle_dir: Path
    fingerprint: str


def set_detected_game_build(game_build: str | None) -> None:
    global _DETECTED_GAME_BUILD
    if game_build and game_build.strip():
        _DETECTED_GAME_BUILD = game_build.strip()


class AutoFailureCapture:
    def __init__(
        self,
        *,
        capture_root: Path | None = None,
        enabled: bool | None = None,
        clock: Callable[[], datetime] = utc_now,
        max_bundles: int = DEFAULT_MAX_BUNDLES,
        dedupe_seconds: int = DEFAULT_DEDUPE_SECONDS,
    ) -> None:
        self._capture_root = capture_root
        self._enabled_override = enabled
        self._clock = clock
        self._max_bundles = max_bundles
        self._dedupe_window = timedelta(seconds=dedupe_seconds)
        self._recent: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def capture(
        self,
        *,
        reason: str,
        image: np.ndarray,
        tts_lines: Sequence[str],
        detail_image: np.ndarray | None = None,
        raw_tts_lines: Sequence[str] | None = None,
        error: BaseException | str | None = None,
        locale: str | None = None,
        game_build: str | None = None,
    ) -> AutoFailureCaptureResult | None:
        if not self._enabled() or image is None or not tts_lines:
            return None

        cleaned_lines = tuple(str(line) for line in tts_lines)
        raw_lines = tuple(str(line) for line in (raw_tts_lines or cleaned_lines))
        locale = locale or IniConfigLoader().general.language
        game_build = game_build or _DETECTED_GAME_BUILD
        fingerprint = self._fingerprint(locale, game_build, reason, cleaned_lines)
        captured_at = self._clock()

        with self._lock:
            self._prune_recent(captured_at)
            previous_capture = self._recent.get(fingerprint)
            if previous_capture is not None and captured_at - previous_capture < self._dedupe_window:
                return None
            self._recent[fingerprint] = captured_at

            capture_root = self._capture_root or IniConfigLoader().user_dir / "captures" / "automatic"
            stem = f"failure-{captured_at.astimezone(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{fingerprint[:10]}"
            bundle_dir = capture_root / stem
            staging_dir = capture_root / f".{stem}.tmp"
            try:
                capture_root.mkdir(parents=True, exist_ok=True)
                staging_dir.mkdir()
                self._write_screenshot(staging_dir / "screenshot.png", image)
                if detail_image is not None:
                    self._write_screenshot(staging_dir / "tooltip.png", detail_image)
                self._write_tts_capture(
                    staging_dir / "tts.jsonl",
                    raw_lines=raw_lines,
                    locale=locale,
                    game_build=game_build,
                    reason=reason,
                    captured_at=captured_at,
                )
                self._write_manifest(
                    staging_dir / "manifest.json",
                    reason=reason,
                    fingerprint=fingerprint,
                    locale=locale,
                    game_build=game_build,
                    captured_at=captured_at,
                    image=image,
                    detail_image=detail_image,
                    tts_lines=cleaned_lines,
                    raw_tts_lines=raw_lines,
                    error=error,
                )
                staging_dir.replace(bundle_dir)
                self._trim_old_bundles(capture_root)
            except OSError, TypeError, ValueError, cv2.error:
                self._recent.pop(fingerprint, None)
                if staging_dir.is_dir():
                    self._remove_known_bundle(staging_dir)
                LOGGER.exception("Could not save automatic parser-failure capture")
                return None

        LOGGER.warning("Saved automatic parser-failure capture to %s", bundle_dir)
        return AutoFailureCaptureResult(bundle_dir=bundle_dir, fingerprint=fingerprint)

    def _enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return IniConfigLoader().general.automatic_failure_capture

    def _prune_recent(self, now: datetime) -> None:
        cutoff = now - self._dedupe_window
        self._recent = {fingerprint: saved_at for fingerprint, saved_at in self._recent.items() if saved_at >= cutoff}

    def _trim_old_bundles(self, capture_root: Path) -> None:
        bundles = sorted(
            (path for path in capture_root.iterdir() if path.is_dir() and path.name.startswith("failure-")),
            key=lambda path: path.name,
        )
        for bundle in bundles[: max(0, len(bundles) - self._max_bundles)]:
            self._remove_known_bundle(bundle)

    @staticmethod
    def _remove_known_bundle(bundle_dir: Path) -> None:
        for filename in _BUNDLE_FILES:
            try:
                (bundle_dir / filename).unlink(missing_ok=True)
            except OSError:
                LOGGER.warning("Could not remove old automatic capture file: %s", bundle_dir / filename)
                return
        try:
            bundle_dir.rmdir()
        except OSError:
            LOGGER.warning("Could not remove automatic capture directory: %s", bundle_dir)

    @staticmethod
    def _write_screenshot(path: Path, image: np.ndarray) -> None:
        encoded, png = cv2.imencode(".png", image)
        if not encoded:
            msg = "OpenCV could not encode the failure screenshot"
            raise OSError(msg)
        path.write_bytes(png.tobytes())

    @staticmethod
    def _write_tts_capture(
        path: Path, *, raw_lines: Sequence[str], locale: str, game_build: str, reason: str, captured_at: datetime
    ) -> None:
        session = CaptureSession(
            session_id=str(uuid.uuid4()),
            started_at=utc_timestamp(captured_at),
            metadata={"category": "automatic-failure", "reason": reason, "capture_source": "desktop-app"},
        )
        records = [
            build_capture_record(
                payload=line.encode("utf-8"),
                locale=locale,
                game_build=game_build,
                session=session,
                sequence=index,
                captured_at=captured_at,
            )
            for index, line in enumerate(raw_lines, start=1)
        ]
        output = "".join(f"{json.dumps(record, ensure_ascii=False, separators=(',', ':'))}\n" for record in records)
        path.write_text(output, encoding="utf-8")

    @staticmethod
    def _write_manifest(
        path: Path,
        *,
        reason: str,
        fingerprint: str,
        locale: str,
        game_build: str,
        captured_at: datetime,
        image: np.ndarray,
        detail_image: np.ndarray | None,
        tts_lines: Sequence[str],
        raw_tts_lines: Sequence[str],
        error: BaseException | str | None,
    ) -> None:
        error_data = None
        if error is not None:
            error_data = {
                "type": type(error).__name__ if isinstance(error, BaseException) else "message",
                "message": str(error),
            }
        manifest = {
            "schema_version": AUTO_CAPTURE_SCHEMA_VERSION,
            "captured_at": utc_timestamp(captured_at),
            "reason": reason,
            "fingerprint": fingerprint,
            "locale": locale,
            "game_build": game_build,
            "app_version": __version__,
            "image": {"file": "screenshot.png", "height": int(image.shape[0]), "width": int(image.shape[1])},
            "detail_image": (
                {"file": "tooltip.png", "height": int(detail_image.shape[0]), "width": int(detail_image.shape[1])}
                if detail_image is not None
                else None
            ),
            "tts": {
                "file": "tts.jsonl",
                "source": "raw-pipe-lines" if tuple(raw_tts_lines) != tuple(tts_lines) else "framed-lines",
                "framed_lines": list(tts_lines),
                "raw_lines": list(raw_tts_lines),
            },
            "error": error_data,
        }
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _fingerprint(locale: str, game_build: str, reason: str, tts_lines: Sequence[str]) -> str:
        payload = "\0".join((locale, game_build, reason, *tts_lines)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


AUTO_FAILURE_CAPTURE = AutoFailureCapture()


def capture_failure(**kwargs) -> AutoFailureCaptureResult | None:
    return AUTO_FAILURE_CAPTURE.capture(**kwargs)
