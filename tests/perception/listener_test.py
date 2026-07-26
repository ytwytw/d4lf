import logging

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
