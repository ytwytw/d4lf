import logging
import queue
import threading
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.locale_data import LocaleGrammar

from src.diagnostics import record_raw_tts
from src.item import Dataloader
from src.perception.backend.core import load_backend
from src.perception.framing import TtsFramer
from src.perception.framing import find_item_start as _find_item_start
from src.perception.framing import fix_data as _fix_data

CONNECTED = False
LAST_ITEM: list[str] = []
LAST_ITEM_RAW: list[str] = []
_DATA_QUEUE = queue.Queue(maxsize=100)
_LAST_ITEM_LOCK = threading.Lock()
_backend = load_backend()
LOGGER = logging.getLogger(__name__)


def find_item_start(
    data: list[str], *, grammar: LocaleGrammar | None = None, catalog: Dataloader | None = None
) -> int | None:
    catalog = catalog or Dataloader()
    return _find_item_start(data, grammar=grammar or catalog.grammar, catalog=catalog)


def filter_data(data: str) -> bool:
    return "Champions who earn the favor of" in data


def fix_data(data: str, *, grammar: LocaleGrammar | None = None) -> str:
    return _fix_data(data, grammar=grammar or Dataloader().grammar)


class Publisher:
    _instance: ClassVar[Publisher | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()
    _item_subscribers: set[Callable[..., None]]
    _info_subscribers: set[Callable[..., None]]
    _subscriber_lock: threading.Lock

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._item_subscribers = set()
                cls._instance._info_subscribers = set()
                cls._instance._subscriber_lock = threading.Lock()
        return cls._instance

    def find_item(self) -> None:
        catalog = Dataloader()
        framer = TtsFramer(catalog.grammar, catalog)
        while True:
            raw_data = _DATA_QUEUE.get()
            try:
                record_raw_tts(raw_data)
                data = fix_data(raw_data, grammar=catalog.grammar)
                if not data:
                    continue
                if "gold" in data.lower() or "experience" in data.lower():
                    self.publish_info(data)

                if catalog.grammar.locale != framer.grammar.locale:
                    framer = TtsFramer(catalog.grammar, catalog)
                if not filter_data(data) and (item_trace := framer.feed(data, raw_data=raw_data)) is not None:
                    global LAST_ITEM, LAST_ITEM_RAW
                    with _LAST_ITEM_LOCK:
                        LAST_ITEM = item_trace
                        LAST_ITEM_RAW = framer.last_raw_item.copy()
                    self.publish_item(LAST_ITEM)
            except Exception:
                LOGGER.exception("TTS line processing failed; continuing with the next line")

    def publish_item(self, data):
        LOGGER.debug("Raw TTS payload: %s", data)
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


def set_connected(value: bool) -> None:
    global CONNECTED
    CONNECTED = value


def get_item_trace_snapshot() -> tuple[list[str], list[str]]:
    with _LAST_ITEM_LOCK:
        return LAST_ITEM.copy(), LAST_ITEM_RAW.copy()


def create_pipe():
    return _backend.create_pipe(LOGGER)


def read_pipe() -> None:
    _backend.read_pipe(create_pipe, _DATA_QUEUE, LOGGER, set_connected)


def start_connection() -> None:
    _backend.start_connection(Publisher().find_item, read_pipe, LOGGER)
