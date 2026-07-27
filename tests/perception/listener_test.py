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


def test_listener_taps_raw_tts_before_framing(monkeypatch) -> None:
    recorded = []
    monkeypatch.setattr(listener, "Dataloader", lambda: SimpleNamespace(grammar=SimpleNamespace(locale="enUS")))
    monkeypatch.setattr(listener, "TtsFramer", lambda *_args: object())
    monkeypatch.setattr(listener._DATA_QUEUE, "get", lambda: "raw tts")
    monkeypatch.setattr(listener, "record_raw_tts", recorded.append)
    monkeypatch.setattr(listener, "fix_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("stop")))

    with pytest.raises(RuntimeError, match="stop"):
        Publisher().find_item()

    assert recorded == ["raw tts"]
