"""Replace highlighting results conservatively for each completed TTS item event."""

import logging
from threading import Event, Thread
from typing import TYPE_CHECKING

from src.diagnostics import capture_latest_failure
from src.perception import capture, parse_item_text

if TYPE_CHECKING:
    from src.loot.highlighting import _VisionModeWithHighlighting

LOGGER = logging.getLogger(__name__)


class HighlightingEvents:
    def on_tts(self: _VisionModeWithHighlighting, data: list[str]) -> None:
        # Invalidate queued drawings before waiting for old work. Tooltip presence
        # at the same position is not proof that this is still the previous item.
        self.current_item = None
        self.request_clear()
        self.stop_thread_and_wait(self.evaluate_item_thread, self.evaluate_item_thread_cancel_event)
        self.stop_thread_and_wait(
            self.clear_when_item_not_selected_thread, self.clear_when_item_not_selected_thread_cancel_event
        )
        self.evaluate_item_thread = None
        self.clear_when_item_not_selected_thread = None
        try:
            item = parse_item_text(data)
        except Exception as error:
            LOGGER.exception("Unable to parse highlighting TTS event: %s", data)
            try:
                capture_latest_failure(reason="highlight-overlay-item-parse", image=capture(), error=error)
            except Exception:
                LOGGER.exception("Unable to capture highlighting parse failure")
            return
        if item is None:
            return
        LOGGER.debug("Parsed item based on TTS: %s", item)
        self.current_item = item
        cancel_event = Event()
        self.evaluate_item_thread_cancel_event = cancel_event
        self.evaluate_item_thread = Thread(
            target=self.evaluate_item_and_queue_draw, args=(item, cancel_event), daemon=True
        )
        self.evaluate_item_thread.start()
