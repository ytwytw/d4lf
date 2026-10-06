import logging
from types import SimpleNamespace

import pytest

from src.perception import listener
from src.perception.listener import Publisher, filter_data, find_item_start, fix_data, get_item_trace_snapshot


def test_listener_identifies_item_start_and_cleans_tts_markers() -> None:
    assert find_item_start(["Noise", "RARE SWORD", "Right mouse button"]) == 1
    assert filter_data("Champions who earn the favor of the season")
    assert fix_data("[MARKED AS JUNK]. [FAVORITED ITEM]. Name") == "Name"


def test_listener_item_publication_logs_raw_tts_payload(caplog) -> None:
    payload = ["RARE SWORD", "Right mouse button"]

    with caplog.at_level(logging.DEBUG, logger="src.perception.listener"):
        Publisher().publish_item(payload)

    assert f"Raw TTS payload: {payload}" in caplog.messages


def test_item_trace_snapshot_is_isolated_from_global_state(monkeypatch) -> None:
    monkeypatch.setattr(listener, "LAST_ITEM", ["clean"])
    monkeypatch.setattr(listener, "LAST_ITEM_RAW", ["raw"])

    clean, raw = get_item_trace_snapshot()
    clean.append("changed")
    raw.append("changed")

    assert listener.LAST_ITEM == ["clean"]
    assert listener.LAST_ITEM_RAW == ["raw"]


def test_listener_recovers_after_one_tts_line_fails(monkeypatch, caplog) -> None:
    monkeypatch.setattr(listener, "_LAST_ITEM_SEQUENCE", 4)
    recorded = []
    published = []
    queued = iter(["bad raw tts", "good raw tts"])

    class Framer:
        grammar = SimpleNamespace(locale="enUS")
        last_raw_item = ["good raw tts"]
        last_raw_start_sequence = 2
        last_item_truncated = False

        def feed(self, data, *, raw_data, raw_sequence=0):
            assert data == "good raw tts"
            assert raw_data == "good raw tts"
            return ["good raw tts"]

    monkeypatch.setattr(listener, "GameCatalog", lambda: SimpleNamespace(grammar=SimpleNamespace(locale="enUS")))
    monkeypatch.setattr(listener, "TtsFramer", lambda *_args: Framer())
    monkeypatch.setattr(listener._DATA_QUEUE, "get", lambda: next(queued))
    monkeypatch.setattr(listener, "record_raw_tts", recorded.append)
    monkeypatch.setattr(
        listener,
        "fix_data",
        lambda data, **_kwargs: (_ for _ in ()).throw(RuntimeError("bad line")) if data.startswith("bad") else data,
    )
    monkeypatch.setattr(Publisher(), "publish_item", published.append)

    with caplog.at_level(logging.ERROR, logger="src.perception.listener"), pytest.raises(StopIteration):
        Publisher().find_item()

    assert recorded == ["bad raw tts", "good raw tts"]
    assert published == [["good raw tts"]]
    assert listener.get_latest_item_snapshot() == (5, ["good raw tts"])
    assert "TTS line processing failed; continuing with the next line" in caplog.messages


def test_latest_item_snapshot_is_a_copy(monkeypatch) -> None:
    monkeypatch.setattr(listener, "LAST_ITEM", ["same item name"])
    monkeypatch.setattr(listener, "_LAST_ITEM_SEQUENCE", 7)
    sequence, lines = listener.get_latest_item_snapshot()
    lines.clear()
    assert sequence == 7
    assert listener.LAST_ITEM == ["same item name"]


def test_complete_snapshot_correlates_raw_and_clean_lines_atomically(monkeypatch) -> None:
    monkeypatch.setattr(listener, "LAST_ITEM", ["clean"])
    monkeypatch.setattr(listener, "LAST_ITEM_RAW", ["[FAVORITED ITEM]. clean"])
    monkeypatch.setattr(listener, "_LAST_ITEM_SEQUENCE", 5)
    monkeypatch.setattr(listener, "_LAST_ITEM_RAW_SEQUENCE", 30)
    monkeypatch.setattr(listener, "_LAST_ITEM_RAW_START_SEQUENCE", 22)
    snapshot = listener.get_complete_item_snapshot()
    assert snapshot.sequence == 5
    assert snapshot.raw_start_sequence == 22
    assert snapshot.raw_sequence == 30
    assert snapshot.raw_lines == ("[FAVORITED ITEM]. clean",)
    listener.LAST_ITEM_RAW.append("later")
    assert snapshot.raw_lines == ("[FAVORITED ITEM]. clean",)


def test_passive_raw_subscription_preserves_unrecognized_text_and_is_detachable() -> None:
    events = []
    publisher = Publisher()
    publisher.subscribe_raw(events.append)
    try:
        first = publisher.publish_raw("\n[MARKED AS JUNK]. 未知物品\n")
    finally:
        publisher.unsubscribe_raw(events.append)
    publisher.publish_raw("later")
    assert events == [first]
    assert first.text == "\n[MARKED AS JUNK]. 未知物品\n"
