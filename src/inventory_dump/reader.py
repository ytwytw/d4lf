"""Correlate each hover with fresh raw TTS, retaining unsuccessful observations."""

import logging
import threading
import time
from typing import TYPE_CHECKING

from src.inventory_dump.exporting import serialize_item
from src.inventory_dump.framing import extract_literal_trace
from src.inventory_dump.observations import ambient_only, observe_favorite, observe_item_fields
from src.perception import Publisher, complete_item_snapshot, fix_data, latest_raw_sequence, parse_item_text

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.inventory_dump.models import ItemRecord
    from src.perception import RawTtsEvent

LOGGER = logging.getLogger(__name__)


class ScanCancelledError(Exception):
    pass


class TtsNotSettledError(Exception):
    pass


class ItemReader:
    def __init__(self, cancel: threading.Event) -> None:
        self.cancel = cancel
        self._lock = threading.Lock()
        self._events: list[RawTtsEvent] = []
        self._last_event_at = 0.0

    def open(self) -> None:
        Publisher().subscribe_raw(self._receive)

    def close(self) -> None:
        Publisher().unsubscribe_raw(self._receive)

    def _receive(self, event: RawTtsEvent) -> None:
        with self._lock:
            self._events.append(event)
            self._last_event_at = event.received_at

    def wait(self, seconds: float) -> None:
        if self.cancel.wait(seconds):
            raise ScanCancelledError

    def settle(self, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.wait(0.1)
            with self._lock:
                last_event = self._last_event_at
            if time.monotonic() - last_event >= 0.3:
                return
        msg = "TTS did not become quiet before the next hover; stopping to avoid mixed item text."
        raise TtsNotSettledError(msg)

    def read(
        self,
        record: ItemRecord,
        hover: Callable[[], None],
        neutral: Callable[[], None],
        *,
        expected_occupied: bool | None = True,
    ) -> None:
        for attempt in range(1, 2 if expected_occupied is False else 3):
            record.attempts = attempt
            neutral()
            self.settle()
            baseline = complete_item_snapshot().sequence
            with self._lock:
                self._events.clear()
            raw_baseline = latest_raw_sequence()
            try:
                hover()
                self._wait_for_trace(record, baseline, raw_baseline, 1.2 if expected_occupied is False else 2.5)
            finally:
                with self._lock:
                    events = [event for event in self._events if event.sequence > raw_baseline]
                if not record.capture_complete:
                    record.raw_tts.extend(event.text for event in events)
                record.raw_events.extend(
                    {
                        "sequence": event.sequence,
                        "text": event.text,
                        "received_at": event.received_at,
                        "attempt": attempt,
                    }
                    for event in events
                )
            if record.capture_complete:
                record.error = None
                self._parse(record)
                return
            if expected_occupied is False and (not record.raw_tts or ambient_only(record.raw_tts)):
                record.status = "empty"
                record.error = None
                return
        record.status = "unparsed" if record.raw_tts else "timeout"
        record.error = "No complete item trace after hovering; all received raw text is retained."
        if record.truncated:
            record.error = "Item framing exceeded its line limit; untruncated raw observation events are retained."

    def _wait_for_trace(self, record: ItemRecord, baseline: int, raw_baseline: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.wait(0.05)
            with self._lock:
                events = [event for event in self._events if event.sequence > raw_baseline]
            if trace := extract_literal_trace(events):
                record.raw_tts = [event.text for event in trace]
                record.normalized_tts = [fix_data(line) for line in record.raw_tts]
                record.raw_sequence_start = trace[0].sequence
                record.raw_sequence_end = trace[-1].sequence
                record.capture_complete = True
                record.truncated = False
                record.capture_source = "literal_item_header_footer"
                return
            snapshot = complete_item_snapshot()
            if snapshot.sequence > baseline and snapshot.raw_start_sequence > raw_baseline:
                record.normalized_tts = list(snapshot.normalized_lines)
                record.raw_tts = list(snapshot.raw_lines)
                record.raw_sequence_start = snapshot.raw_start_sequence
                record.raw_sequence_end = snapshot.raw_sequence
                record.truncated = snapshot.truncated
                record.capture_complete = not snapshot.truncated
                record.capture_source = "shared_tts_framer"
                return

    @staticmethod
    def _parse(record: ItemRecord) -> None:
        favorite = observe_favorite(record.raw_tts)
        record.favorite = True if favorite is not None else None
        if favorite is not None:
            record.favorite_evidence.append(favorite)
        record.observed_fields = observe_item_fields(record.raw_tts)
        try:
            item = parse_item_text(record.normalized_tts)
            if item is None:
                record.status = "unparsed"
                record.error = "The parser does not recognize this item; raw TTS is retained."
            else:
                record.parsed = serialize_item(item)
                record.status = "parsed"
        except Exception as error:
            LOGGER.exception("Inventory item parsing failed at %s", record.location.label)
            record.status = "parse_error"
            record.error = f"{type(error).__name__}: {error}"
