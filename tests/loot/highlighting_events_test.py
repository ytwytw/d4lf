from threading import Event

import pytest

from src.item import Item
from src.loot import highlighting_events as events
from src.loot.highlighting import _VisionModeWithHighlighting


def _worker(mocker):
    worker = object.__new__(_VisionModeWithHighlighting)
    worker.current_item = Item(name="previous_kept_item")
    worker.request_clear = mocker.Mock()
    worker.evaluate_item_thread = mocker.Mock()
    worker.evaluate_item_thread.is_alive.return_value = False
    worker.evaluate_item_thread_cancel_event = Event()
    worker.clear_when_item_not_selected_thread = mocker.Mock()
    worker.clear_when_item_not_selected_thread.is_alive.return_value = False
    worker.clear_when_item_not_selected_thread_cancel_event = Event()
    return worker


@pytest.mark.parametrize("raises", [False, True])
def test_unknown_tooltip_replacing_known_item_clears_marks_and_cancels_old_work(monkeypatch, mocker, raises) -> None:
    worker = _worker(mocker)
    old_evaluator = worker.evaluate_item_thread
    old_watcher = worker.clear_when_item_not_selected_thread
    thread_factory = mocker.patch.object(events, "Thread")
    parser = mocker.patch.object(events, "parse_item_text", return_value=None)
    if raises:
        parser.side_effect = ValueError("unknown tooltip")
    monkeypatch.setattr(events, "capture", lambda: None)
    monkeypatch.setattr(events, "capture_latest_failure", lambda **_: None)

    worker.on_tts(["unknown item at the same screen position"])

    assert worker.current_item is None
    assert worker.evaluate_item_thread_cancel_event.is_set()
    assert worker.clear_when_item_not_selected_thread_cancel_event.is_set()
    old_evaluator.join.assert_called_once_with(timeout=2)
    old_watcher.join.assert_called_once_with(timeout=2)
    worker.request_clear.assert_called_once_with()
    thread_factory.assert_not_called()


def test_highlighting_parses_the_callback_payload_not_the_global_latest_item(mocker) -> None:
    worker = _worker(mocker)
    incoming = ["actual callback item"]
    item = Item(name="actual callback item")
    parser = mocker.patch.object(events, "parse_item_text", return_value=item)
    thread_factory = mocker.patch.object(events, "Thread")

    worker.on_tts(incoming)

    parser.assert_called_once_with(incoming)
    assert worker.current_item is item
    assert thread_factory.call_args.kwargs["args"][0] is item
    thread_factory.return_value.start.assert_called_once_with()
