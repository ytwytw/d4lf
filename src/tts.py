from __future__ import annotations

import logging
import queue
import sys
import threading
from typing import TYPE_CHECKING

from src import tts_backend_noop
from src.config.helper import singleton
from src.dataloader import Dataloader
from src.diagnostics.tts_capture import APP_TTS_CAPTURE
from src.tts_framing import TtsFramer, fix_data
from src.tts_framing import find_item_start as _find_item_start

if TYPE_CHECKING:
    from src.locale_data import LocaleGrammar

if sys.platform == "win32":
    from src import tts_backend_windows as _backend
else:
    _backend = tts_backend_noop

CONNECTED = False
LAST_ITEM = []
LAST_ITEM_RAW = []
TO_FILTER = ["Champions who earn the favor of"]
_DATA_QUEUE = queue.Queue(maxsize=100)
_LAST_ITEM_LOCK = threading.Lock()
_PIPE_DISCONNECTED_ERRORS = frozenset({109, 232, 233})
_PIPE_ALREADY_CONNECTED = 535
_PIPE_RECONNECT_DELAY_SECONDS = 0.1

LOGGER = logging.getLogger(__name__)


@singleton
class Publisher:
    def __init__(self):
        self._item_subscribers = set()
        self._info_subscribers = set()
        self._subscriber_lock = threading.Lock()

    def find_item(self) -> None:
        catalog = Dataloader()
        framer = TtsFramer(catalog.grammar, catalog)
        while True:
            raw_data = _DATA_QUEUE.get()
            data = fix_data(raw_data, grammar=catalog.grammar)
            if not data:
                continue
            # Pass numerical stat lines directly to info subscribers (Gold/Exp)
            if "gold" in data.lower() or "experience" in data.lower():
                self.publish_info(data)

            if catalog.grammar.locale != framer.grammar.locale:
                framer = TtsFramer(catalog.grammar, catalog)
            if not filter_data(data) and (item_trace := framer.feed(data, raw_data=raw_data)) is not None:
                global LAST_ITEM, LAST_ITEM_RAW
                with _LAST_ITEM_LOCK:
                    LAST_ITEM = item_trace
                    LAST_ITEM_RAW = framer.last_raw_item.copy()
                LOGGER.debug(f"TTS Found: {LAST_ITEM}")
                self.publish_item(LAST_ITEM)

    def publish_item(self, data):
        with self._subscriber_lock:
            subscribers = tuple(self._item_subscribers)
        for subscriber in subscribers:
            try:
                subscriber(data)
            except Exception:
                LOGGER.exception("TTS item subscriber failed: %r", subscriber)

    def subscribe_item(self, subscriber):
        with self._subscriber_lock:
            self._item_subscribers.add(subscriber)

    def unsubscribe_item(self, subscriber):
        with self._subscriber_lock:
            self._item_subscribers.discard(subscriber)

    def publish_info(self, data):
        with self._subscriber_lock:
            subscribers = tuple(self._info_subscribers)
        for subscriber in subscribers:
            try:
                subscriber(data)
            except Exception:
                LOGGER.exception("TTS info subscriber failed: %r", subscriber)

    def subscribe_info(self, subscriber):
        with self._subscriber_lock:
            self._info_subscribers.add(subscriber)

    def unsubscribe_info(self, subscriber):
        with self._subscriber_lock:
            self._info_subscribers.discard(subscriber)


def _set_connected(value: bool) -> None:
    global CONNECTED
    CONNECTED = value


def create_pipe():
    return _backend.create_pipe(LOGGER)


def record_and_decode_pipe_payload(payload: bytes) -> str:
    APP_TTS_CAPTURE.record_payload(payload)
    return payload.decode("utf-8").replace("\x00", "")


def get_item_trace_snapshot() -> tuple[list[str], list[str]]:
    with _LAST_ITEM_LOCK:
        return LAST_ITEM.copy(), LAST_ITEM_RAW.copy()


def raw_trace_for(tts_lines: list[str]) -> list[str]:
    with _LAST_ITEM_LOCK:
        return LAST_ITEM_RAW.copy() if tts_lines == LAST_ITEM and LAST_ITEM_RAW else tts_lines.copy()


def is_equipment_trace(tts_lines: list[str]) -> bool:
    """Return whether a framed trace contains the locale's item-power marker."""
    grammar = Dataloader().grammar
    return any(grammar.contains("item_power", line) for line in tts_lines[:10])


def read_pipe(
    *, stop_event: threading.Event | None = None, reconnect_delay: float = _PIPE_RECONNECT_DELAY_SECONDS
) -> None:
    _backend.read_pipe(
        create_pipe,
        _DATA_QUEUE,
        LOGGER,
        _set_connected,
        record_and_decode_pipe_payload,
        stop_event=stop_event,
        reconnect_delay=reconnect_delay,
    )


def find_item_start(data: list[str], *, grammar: LocaleGrammar | None = None, catalog=None) -> int | None:
    catalog = catalog or Dataloader()
    grammar = grammar or catalog.grammar
    return _find_item_start(data, grammar=grammar, catalog=catalog)


def filter_data(data: str) -> bool:
    return any(word in data for word in TO_FILTER)


def start_connection() -> None:
    _backend.start_connection(Publisher().find_item, read_pipe, LOGGER)
