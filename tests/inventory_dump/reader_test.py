from threading import Event
from typing import TYPE_CHECKING

import pytest

from src.inventory_dump.models import ItemRecord, Location, ScanDocument
from src.inventory_dump.reader import ItemReader, ScanCancelledError, TtsNotSettledError
from src.item import Item
from src.perception import ItemTraceSnapshot, Publisher

if TYPE_CHECKING:
    from src.type_aliases import JsonObject


def _reader(monkeypatch):
    cancel = Event()
    reader = ItemReader(cancel)
    clock = [100.0]
    monkeypatch.setattr("src.inventory_dump.reader.time.monotonic", lambda: clock[0])

    def wait(seconds):
        if cancel.is_set():
            raise ScanCancelledError
        clock[0] += seconds

    monkeypatch.setattr(reader, "wait", wait)
    monkeypatch.setattr(reader, "settle", lambda **_: None)
    reader.open()
    return reader, cancel


def test_fresh_unknown_tts_is_retained_even_when_parser_raises(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    snapshot = [ItemTraceSnapshot(0, (), (), 0, 0)]
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: snapshot[0])
    monkeypatch.setattr(
        "src.inventory_dump.reader.parse_item_text", lambda _: (_ for _ in ()).throw(ValueError("new item"))
    )

    def hover():
        event = Publisher().publish_raw("[FAVORITED ITEM]. Unknown 新物品")
        snapshot[0] = ItemTraceSnapshot(
            1, ("Unknown 新物品",), (event.text,), event.sequence, event.received_at, event.sequence
        )

    record = ItemRecord(Location("stash", "1", "r01c01", (5, 5)))
    try:
        reader.read(record, hover, lambda: None)
    finally:
        reader.close()
    assert record.status == "parse_error"
    assert record.raw_tts == ["[FAVORITED ITEM]. Unknown 新物品"]
    assert record.error == "ValueError: new item"
    assert record.favorite
    assert record.observed_fields is not None
    assert record.observed_fields["name_text"] == "Unknown 新物品"
    assert record.observed_fields["catalog_mapped"] is False


def test_repeated_names_require_new_completed_sequence(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    monkeypatch.setattr(
        "src.inventory_dump.reader.complete_item_snapshot", lambda: ItemTraceSnapshot(8, ("same",), ("same",), 99, 0)
    )
    parse = []
    monkeypatch.setattr("src.inventory_dump.reader.parse_item_text", lambda lines: parse.append(lines) or Item())
    record = ItemRecord(Location("inventory", "equipment", "r01c02", (5, 5)))
    try:
        reader.read(record, lambda: None, lambda: None)
    finally:
        reader.close()
    assert record.status == "timeout"
    assert record.normalized_tts == []
    assert not parse


def test_cancel_keeps_raw_received_before_incomplete_item(monkeypatch) -> None:
    reader, cancel = _reader(monkeypatch)
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: ItemTraceSnapshot(0, (), (), 0, 0))

    def hover():
        Publisher().publish_raw("unfinished raw item")
        cancel.set()

    record = ItemRecord(Location("equipped", "talisman", "seal", (5, 5)))
    try:
        with pytest.raises(ScanCancelledError):
            reader.read(record, hover, lambda: None)
    finally:
        reader.close()
    assert record.raw_tts == ["unfinished raw item"]
    assert not record.capture_complete


def test_unframed_raw_text_is_kept_and_does_not_become_an_empty_slot(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: ItemTraceSnapshot(0, (), (), 0, 0))
    record = ItemRecord(Location("inventory", "keys", "r01c01", (5, 5)))
    try:
        reader.read(record, lambda: Publisher().publish_raw("未知钥匙数量 3"), lambda: None, expected_occupied=False)
    finally:
        reader.close()
    assert record.status == "unparsed"
    assert record.raw_tts == ["未知钥匙数量 3"]


def test_frame_started_before_hover_is_rejected_even_if_it_finishes_afterward(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    snapshot = [ItemTraceSnapshot(1, (), (), 1, 0, 1)]
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: snapshot[0])
    monkeypatch.setattr("src.inventory_dump.reader.latest_raw_sequence", lambda: 10)

    def hover():
        snapshot[0] = ItemTraceSnapshot(2, ("old slot",), ("old slot",), 15, 100, 8)

    record = ItemRecord(Location("inventory", "equipment", "r01c02", (5, 5)))
    try:
        reader.read(record, hover, lambda: None)
    finally:
        reader.close()
    assert record.status == "timeout"
    assert record.normalized_tts == []
    assert not record.capture_complete


def test_continuous_tts_does_not_allow_the_next_hover(monkeypatch) -> None:
    cancel = Event()
    reader = ItemReader(cancel)
    clock = [100.0]
    monkeypatch.setattr("src.inventory_dump.reader.time.monotonic", lambda: clock[0])

    def wait(seconds):
        clock[0] += seconds
        reader._last_event_at = clock[0]

    monkeypatch.setattr(reader, "wait", wait)
    with pytest.raises(TtsNotSettledError, match="did not become quiet"):
        reader.settle(timeout=0.5)


def test_successful_snapshot_raw_does_not_include_unrelated_later_callbacks(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    snapshot = [ItemTraceSnapshot(0, (), (), 0, 0)]
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: snapshot[0])
    monkeypatch.setattr("src.inventory_dump.reader.parse_item_text", lambda _: Item(original_name="correct item"))

    def hover():
        event = Publisher().publish_raw("correct item")
        snapshot[0] = ItemTraceSnapshot(
            1, (event.text,), (event.text,), event.sequence, event.received_at, event.sequence
        )
        Publisher().publish_raw("unrelated UI announcement")

    record = ItemRecord(Location("inventory", "equipment", "r01c01", (5, 5)))
    try:
        reader.read(record, hover, lambda: None)
    finally:
        reader.close()
    assert record.status == "parsed"
    assert record.raw_tts == ["correct item"]
    assert [event["text"] for event in record.raw_events] == ["correct item", "unrelated UI announcement"]


def test_event_published_during_raw_baseline_read_is_not_cleared(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: ItemTraceSnapshot(0, (), (), 0, 0))

    def baseline():
        event = Publisher().publish_raw("new raw item during baseline read")
        return event.sequence - 1

    monkeypatch.setattr("src.inventory_dump.reader.latest_raw_sequence", baseline)
    record = ItemRecord(Location("inventory", "keys", "r01c01", (5, 5)))
    try:
        reader.read(record, lambda: None, lambda: None, expected_occupied=False)
    finally:
        reader.close()
    assert record.status == "unparsed"
    assert record.raw_tts == ["new raw item during baseline read"]


@pytest.mark.parametrize("text", ["Höpe | 70 (133)", "&lt;POTATO&gt; Nadjia | 70 (174)"])
def test_town_player_broadcast_on_visually_empty_slot_is_not_an_item(monkeypatch, text) -> None:
    reader, _ = _reader(monkeypatch)
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: ItemTraceSnapshot(0, (), (), 0, 0))
    record = ItemRecord(Location("stash", "1", "r04c04", (5, 5)))
    try:
        reader.read(record, lambda: Publisher().publish_raw(text), lambda: None, expected_occupied=False)
    finally:
        reader.close()
    assert record.status == "empty"
    assert record.error is None
    assert not record.capture_complete


def test_incomplete_item_plus_player_broadcast_is_preserved_on_visual_empty_slot(monkeypatch) -> None:
    reader, _ = _reader(monkeypatch)
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: ItemTraceSnapshot(0, (), (), 0, 0))

    def hover():
        for text in ("Höpe | 70 (133)", "新物品", "先祖暗金头盔", "900 物品强度"):
            Publisher().publish_raw(text)

    record = ItemRecord(Location("stash", "1", "r04c04", (5, 5)))
    try:
        reader.read(record, hover, lambda: None, expected_occupied=False)
    finally:
        reader.close()
    assert record.status == "unparsed"
    assert "新物品" in record.raw_tts


@pytest.mark.parametrize("truncated_first", [False, True])
@pytest.mark.parametrize("catalog_parsed", [False, True])
def test_complete_rune_trace_replaces_truncated_frame(monkeypatch, truncated_first, catalog_parsed) -> None:
    reader, _ = _reader(monkeypatch)
    snapshot = [ItemTraceSnapshot(0, (), (), 0, 0)]
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: snapshot[0])
    monkeypatch.setattr("src.inventory_dump.reader.parse_item_text", lambda _: Item() if catalog_parsed else None)
    lines = ["安姆 (5)", "暗金仪祭符文", "获得：4 份供品", "造成荆棘伤害。", "鼠标右键"]

    def hover():
        if truncated_first and snapshot[0].sequence == 0:
            event = Publisher().publish_raw("incomplete first attempt")
            snapshot[0] = ItemTraceSnapshot(
                1, (event.text,), (event.text,), event.sequence, event.received_at, event.sequence, truncated=True
            )
            return
        events = [Publisher().publish_raw(line) for line in lines]
        snapshot[0] = ItemTraceSnapshot(
            snapshot[0].sequence + 1,
            tuple(lines[2:]),
            tuple(lines[2:]),
            events[-1].sequence,
            1.0,
            events[2].sequence,
            truncated=True,
        )

    record = ItemRecord(Location("stash", "6", "r01c02", (5, 5)), error="previous capture failure")
    try:
        reader.read(record, hover, lambda: None)
    finally:
        reader.close()
    assert record.capture_complete
    assert not record.truncated
    assert record.attempts == (2 if truncated_first else 1)
    assert ScanDocument("zhCN", "test", items=[record]).failed_count == 0
    assert [event["text"] for event in record.raw_events] == (
        ["incomplete first attempt"] if truncated_first else []
    ) + lines
    assert record.capture_source == "literal_item_header_footer"
    assert record.raw_tts == lines
    assert record.normalized_tts == lines
    assert record.status == ("parsed" if catalog_parsed else "unparsed")
    assert (record.error is None) is catalog_parsed
    assert record.observed_fields is not None
    assert record.observed_fields["name_text"] == "安姆 (5)"
    assert record.observed_fields["quantity"] == 5


@pytest.mark.parametrize(
    ("title", "expected"), [("李奥瑞克的王冠", None), ("地狱火炬", None), ("[收藏物品]. 谜团", True)]
)
@pytest.mark.parametrize("parser_result", ["parsed", "unparsed", "parse_error"])
def test_only_tts_confirms_favorite_independently_of_catalog_and_visual_result(
    monkeypatch, title, expected, parser_result
):
    def parse(_lines):
        if parser_result == "parse_error":
            message = "Unknown item"
            raise ValueError(message)
        return Item(original_name="sample") if parser_result == "parsed" else None

    monkeypatch.setattr("src.inventory_dump.reader.parse_item_text", parse)
    visual: JsonObject = {
        "source": "slot_screenshot_brightness",
        "verification": "unverified",
        "value": expected is not True,
    }
    lines = [title, "先祖暗金胸甲", "900 物品强度", "鼠标右键"]
    record = ItemRecord(
        Location("stash", "2", "r01c08", (5, 5)),
        junk_evidence=[{"source": "slot_screenshot_template", "verification": "unverified", "value": True}],
        raw_tts=list(lines),
        normalized_tts=list(lines),
        capture_complete=True,
        favorite_evidence=[visual],
    )
    ItemReader._parse(record)
    assert record.favorite is expected
    # A visual junk guess never becomes a confirmed state without the spoken title marker.
    assert record.junk is None
    assert record.junk_evidence == [{"source": "slot_screenshot_template", "verification": "unverified", "value": True}]
    assert record.status == parser_result
    assert record.raw_tts == lines
    assert record.favorite_evidence[0] == visual
    assert len(record.favorite_evidence) == (2 if expected else 1)
    if expected:
        assert record.favorite_evidence[1]["source"] == "raw_tts_title"
