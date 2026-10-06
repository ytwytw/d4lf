import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.locale_data import LocaleGrammar

from src.diagnostics import record_raw_tts
from src.game_data import GameCatalog
from src.perception.backend.core import load_backend
from src.perception.framing import TtsFramer
from src.perception.framing import find_item_start as _find_item_start
from src.perception.framing import fix_data as _fix_data

CONNECTED = False
LAST_ITEM: list[str] = []
LAST_ITEM_RAW: list[str] = []
_LAST_ITEM_SEQUENCE = 0
_RAW_SEQUENCE = 0
_LAST_ITEM_RAW_SEQUENCE = 0
_LAST_ITEM_COMPLETED_AT = 0.0
_LAST_ITEM_RAW_START_SEQUENCE = 0
_LAST_ITEM_TRUNCATED = False
_DATA_QUEUE = queue.Queue(maxsize=100)
_LAST_ITEM_LOCK = threading.Lock()
_backend = load_backend()
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RawTtsEvent:
    sequence: int
    text: str
    received_at: float


@dataclass(frozen=True, slots=True)
class ItemTraceSnapshot:
    sequence: int
    normalized_lines: tuple[str, ...]
    raw_lines: tuple[str, ...]
    raw_sequence: int
    completed_at: float
    raw_start_sequence: int = 0
    truncated: bool = False


def find_item_start(
    data: list[str], *, grammar: LocaleGrammar | None = None, catalog: GameCatalog | None = None
) -> int | None:
    catalog = catalog or GameCatalog()
    return _find_item_start(data, grammar=grammar or catalog.grammar, catalog=catalog)


def filter_data(data: str) -> bool:
    return "Champions who earn the favor of" in data


def fix_data(data: str, *, grammar: LocaleGrammar | None = None) -> str:
    return _fix_data(data, grammar=grammar or GameCatalog().grammar)


class Publisher:
    _instance: ClassVar[Self | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()
    _item_subscribers: set[Callable[..., None]]
    _info_subscribers: set[Callable[..., None]]
    _raw_subscribers: set[Callable[[RawTtsEvent], None]]
    _subscriber_lock: threading.Lock

    def __new__(cls) -> Self:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._item_subscribers = set()
                cls._instance._info_subscribers = set()
                cls._instance._raw_subscribers = set()
                cls._instance._subscriber_lock = threading.Lock()
        return cls._instance

    def find_item(self) -> None:
        catalog = GameCatalog()
        framer = TtsFramer(catalog.grammar, catalog)
        while True:
            raw_data = _DATA_QUEUE.get()
            try:
                raw_event = self.publish_raw(raw_data)
                record_raw_tts(raw_data)
                data = fix_data(raw_data, grammar=catalog.grammar)
                if not data:
                    continue
                if "gold" in data.lower() or "experience" in data.lower():
                    self.publish_info(data)

                if catalog.grammar.locale != framer.grammar.locale:
                    framer = TtsFramer(catalog.grammar, catalog)
                if (
                    not filter_data(data)
                    and (item_trace := framer.feed(data, raw_data=raw_data, raw_sequence=raw_event.sequence))
                    is not None
                ):
                    global \
                        LAST_ITEM, \
                        LAST_ITEM_RAW, \
                        _LAST_ITEM_SEQUENCE, \
                        _LAST_ITEM_RAW_SEQUENCE, \
                        _LAST_ITEM_COMPLETED_AT, \
                        _LAST_ITEM_RAW_START_SEQUENCE, \
                        _LAST_ITEM_TRUNCATED
                    with _LAST_ITEM_LOCK:
                        LAST_ITEM = item_trace
                        LAST_ITEM_RAW = framer.last_raw_item.copy()
                        _LAST_ITEM_SEQUENCE += 1
                        _LAST_ITEM_RAW_SEQUENCE = raw_event.sequence
                        _LAST_ITEM_COMPLETED_AT = raw_event.received_at
                        _LAST_ITEM_RAW_START_SEQUENCE = framer.last_raw_start_sequence
                        _LAST_ITEM_TRUNCATED = framer.last_item_truncated
                    self.publish_item(LAST_ITEM)
            except Exception:
                LOGGER.exception("TTS line processing failed; continuing with the next line")

    def publish_item(self, data: list[str]) -> None:
        LOGGER.debug("Raw TTS payload: %s", data)
        with self._subscriber_lock:
            subscribers = tuple(self._item_subscribers)
        for subscriber in subscribers:
            try:
                subscriber(data)
            except Exception:
                LOGGER.exception("TTS item subscriber failed: %r", subscriber)

    def subscribe_item(self, subscriber: Callable[[list[str]], None]) -> None:
        with self._subscriber_lock:
            self._item_subscribers.add(subscriber)

    def unsubscribe_item(self, subscriber: Callable[[list[str]], None]) -> None:
        with self._subscriber_lock:
            self._item_subscribers.discard(subscriber)

    def publish_raw(self, text: str) -> RawTtsEvent:
        """Publish unmodified text even when item framing or parsing fails."""
        global _RAW_SEQUENCE
        with _LAST_ITEM_LOCK:
            _RAW_SEQUENCE += 1
            event = RawTtsEvent(_RAW_SEQUENCE, text, time.monotonic())
        with self._subscriber_lock:
            subscribers = tuple(self._raw_subscribers)
        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:
                LOGGER.exception("Raw TTS subscriber failed: %r", subscriber)
        return event

    def subscribe_raw(self, subscriber: Callable[[RawTtsEvent], None]) -> None:
        with self._subscriber_lock:
            self._raw_subscribers.add(subscriber)

    def unsubscribe_raw(self, subscriber: Callable[[RawTtsEvent], None]) -> None:
        with self._subscriber_lock:
            self._raw_subscribers.discard(subscriber)

    def publish_info(self, data: str) -> None:
        with self._subscriber_lock:
            subscribers = tuple(self._info_subscribers)
        for subscriber in subscribers:
            try:
                subscriber(data)
            except Exception:
                LOGGER.exception("TTS info subscriber failed: %r", subscriber)

    def subscribe_info(self, subscriber: Callable[[str], None]) -> None:
        with self._subscriber_lock:
            self._info_subscribers.add(subscriber)

    def unsubscribe_info(self, subscriber: Callable[[str], None]) -> None:
        with self._subscriber_lock:
            self._info_subscribers.discard(subscriber)


def set_connected(value: bool) -> None:
    global CONNECTED
    CONNECTED = value


def get_item_trace_snapshot() -> tuple[list[str], list[str]]:
    with _LAST_ITEM_LOCK:
        return LAST_ITEM.copy(), LAST_ITEM_RAW.copy()


def get_latest_item_snapshot() -> tuple[int, list[str]]:
    """Atomically pair a completed item's sequence with its text, including repeated names."""
    with _LAST_ITEM_LOCK:
        return _LAST_ITEM_SEQUENCE, LAST_ITEM.copy()


def get_complete_item_snapshot() -> ItemTraceSnapshot:
    """Atomically correlate normalized text with its raw trace and sequence."""
    with _LAST_ITEM_LOCK:
        return ItemTraceSnapshot(
            _LAST_ITEM_SEQUENCE,
            tuple(LAST_ITEM),
            tuple(LAST_ITEM_RAW),
            _LAST_ITEM_RAW_SEQUENCE,
            _LAST_ITEM_COMPLETED_AT,
            _LAST_ITEM_RAW_START_SEQUENCE,
            _LAST_ITEM_TRUNCATED,
        )


def latest_raw_sequence() -> int:
    with _LAST_ITEM_LOCK:
        return _RAW_SEQUENCE


def create_pipe() -> int:
    return _backend.create_pipe(LOGGER)


def read_pipe() -> None:
    _backend.read_pipe(create_pipe, _DATA_QUEUE, LOGGER, set_connected)


def start_connection() -> None:
    _backend.start_connection(Publisher().find_item, read_pipe, LOGGER)
