from threading import Event
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from src.inventory_dump.models import ItemRecord, Location
from src.inventory_dump.outcomes import (
    OCCUPIED_TIMEOUT,
    VISUALLY_EMPTY_TIMEOUT,
    apply_title_markers,
    attempt_timeouts,
    best_observation,
    classify_without_frame,
    restore_title,
)
from src.inventory_dump.reader import ItemReader
from src.item import Item
from src.perception import ItemTraceSnapshot, Publisher, RawTtsEvent

if TYPE_CHECKING:
    from src.type_aliases import JsonObject

RUNE = ["安姆 (5)", "暗金仪祭符文", "获得：4 份供品", "鼠标右键"]
SIGIL = ["耳语密窟梦魇符印", "梦魇符印", "将该地下城转化为. 一个梦魇地下城", "耳语密窟在干燥平原当中", "鼠标右键"]
GRID: tuple[str, str, str] = ("stash", "1", "r01c01")
TALISMAN: tuple[str, str, str] = ("equipped", "talisman", "charm_top")


def test_visually_empty_slots_only_shorten_the_first_hover() -> None:
    assert attempt_timeouts(False) == (VISUALLY_EMPTY_TIMEOUT, OCCUPIED_TIMEOUT)
    assert attempt_timeouts(True) == attempt_timeouts(None) == (OCCUPIED_TIMEOUT, OCCUPIED_TIMEOUT)


@pytest.mark.parametrize(
    ("where", "expected_occupied", "heard", "status"),
    [
        (GRID, False, [[], []], "empty"),
        (GRID, False, [["Höpe | 70 (133)"], ["电池充电中"]], "empty"),
        (GRID, False, [[], ["新物品"]], "unparsed"),
        (GRID, None, [[], []], "unverified"),  # grid icons never settled: dark pixels prove nothing
        (GRID, True, [[], []], "timeout"),  # genuine item timeout: settled pixels say occupied
        (GRID, None, [["神符"], []], "unparsed"),  # equipped labels mean nothing on a grid slot
        (TALISMAN, None, [[], []], "unverified"),
        (TALISMAN, None, [["神符"], ["神符", "电池充电中"]], "unverified"),  # own label alone proves nothing
        (TALISMAN, None, [["神符", "已装备"], []], "unparsed"),
        (TALISMAN, None, [["颈部"], []], "unparsed"),  # another slot's label is not evidence for this one
        (("equipped", "talisman", "seal"), None, [[], ["封印"]], "unverified"),
        (("equipped", "equipment", "weapon_right"), None, [["副手"], []], "unverified"),
    ],
)
def test_only_text_proves_an_item_and_only_explicit_evidence_proves_empty(where, expected_occupied, heard, status):
    scope, page, slot = where
    record = ItemRecord(Location(scope, page, slot, (5, 5)))
    classify_without_frame(record, heard, expected_occupied)
    assert record.status == status
    assert (record.error is None) is (status == "empty")


def test_truncated_text_keeps_its_own_reason() -> None:
    record = ItemRecord(Location(*GRID, (5, 5)), truncated=True)
    classify_without_frame(record, [["谜团", "鼠标右键"]], True)
    assert record.status == "unparsed"
    assert "line limit" in (record.error or "")


def test_raw_tts_is_the_most_informative_single_attempt() -> None:
    assert best_observation([["谜团", "先祖暗金胸甲"], ["谜团"]]) == ["谜团", "先祖暗金胸甲"]
    assert best_observation([["谜团"], ["谜团2"]]) == ["谜团2"]
    assert best_observation([["Höpe | 70 (133)"], []]) == []


def _events(lines: list[str], first_sequence: int = 10) -> list[RawTtsEvent]:
    return [RawTtsEvent(first_sequence + index, line, 1.0) for index, line in enumerate(lines)]


@pytest.mark.parametrize(
    ("spoken", "frame_start", "restored"),
    [
        (SIGIL, 1, True),
        (["头部", "已装备", "李奥瑞克的王冠", "先祖 神话暗金头盔", "鼠标右键"], 2, False),
        (["耳语密窟梦魇符印", "Höpe | 70 (133)", *SIGIL[1:]], 2, False),
        (["新物品", *SIGIL[1:]], 1, False),
    ],
)
def test_only_an_adjacent_title_ending_with_the_frame_title_is_restored(spoken, frame_start, restored) -> None:
    events = _events(spoken)
    framed = tuple(spoken[frame_start:])
    snapshot = ItemTraceSnapshot(1, framed, framed, events[-1].sequence, 1.0, events[frame_start].sequence)
    record = ItemRecord(Location("inventory", "keys", "r02c04", (5, 5)), raw_tts=list(framed))
    restore_title(record, events, snapshot)
    assert record.raw_tts == (spoken[frame_start - 1 :] if restored else list(framed))
    assert (record.raw_reconstruction is not None) is restored


@pytest.mark.parametrize(
    ("title", "favorite", "junk"),
    [
        ("[标记为垃圾]. 谜团", None, True),
        ("[MARKED AS JUNK]. Unknown item", None, True),
        ("[收藏物品]. 谜团", True, None),
        ("[收藏物品]. [标记为垃圾]. 谜团", None, None),
        ("谜团", None, None),
    ],
)
def test_favorite_and_junk_need_an_explicit_current_title_marker(title, favorite, junk) -> None:
    visual: JsonObject = {"source": "slot_screenshot_template", "verification": "unverified", "value": False}
    record = ItemRecord(Location(*GRID, (5, 5)), raw_tts=[title, "先祖暗金胸甲"], junk_evidence=[visual])
    apply_title_markers(record)
    assert (record.favorite, record.junk) == (favorite, junk)
    assert record.junk_evidence[0] == visual
    assert len(record.junk_evidence) == (2 if junk else 1)


@pytest.fixture
def harness(monkeypatch):
    reader = ItemReader(Event())
    clock = [100.0]
    snapshot = [ItemTraceSnapshot(0, (), (), 0, 0)]
    monkeypatch.setattr("src.inventory_dump.reader.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(reader, "wait", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(reader, "settle", lambda **_: None)
    monkeypatch.setattr("src.inventory_dump.reader.complete_item_snapshot", lambda: snapshot[0])
    monkeypatch.setattr("src.inventory_dump.reader.parse_item_text", lambda lines: Item(original_name=lines[0]))
    reader.open()
    yield SimpleNamespace(reader=reader, clock=clock, snapshot=snapshot)
    reader.close()


def _read(
    harness,
    spoken_by_attempt: dict[int, list[str]],
    expected_occupied,
    frame_start: int | None = None,
    where: tuple[str, str, str] = GRID,
):
    hovers = []

    def hover() -> None:
        hovers.append(harness.clock[0])
        spoken = spoken_by_attempt.get(len(hovers), [])
        events = [Publisher().publish_raw(line) for line in spoken]
        if frame_start is not None and events:
            framed = tuple(spoken[frame_start:])
            harness.snapshot[0] = ItemTraceSnapshot(
                len(hovers), framed, framed, events[-1].sequence, 1.0, events[frame_start].sequence, frame_start < 0
            )

    record = ItemRecord(Location(*where, (5, 5)))
    harness.reader.read(record, hover, lambda: None, expected_occupied=expected_occupied)
    return record, hovers


def test_silent_first_hover_of_a_visually_empty_slot_is_recovered_with_the_full_bound(harness) -> None:
    # Live zhcn6: occupied slots produced no TTS on the first hover and were only read on the retry.
    record, hovers = _read(harness, {2: RUNE}, expected_occupied=False)
    assert hovers[1] - hovers[0] == pytest.approx(VISUALLY_EMPTY_TIMEOUT, abs=0.06)
    assert (record.status, record.capture_complete, record.raw_tts) == ("parsed", True, RUNE)


def test_visually_empty_needs_a_short_and_a_full_silent_hover(harness) -> None:
    start = harness.clock[0]
    record, hovers = _read(harness, {}, expected_occupied=False)
    assert (record.status, record.attempts, len(hovers)) == ("empty", 2, 2)
    assert harness.clock[0] - start == pytest.approx(VISUALLY_EMPTY_TIMEOUT + OCCUPIED_TIMEOUT, abs=0.11)


def test_unsettled_grid_silence_is_unverified(harness) -> None:
    record, _ = _read(harness, {}, expected_occupied=None)
    assert record.status == "unverified"


def test_truncated_shared_frame_keeps_one_copy_per_observation(harness) -> None:
    lines = ["谜团", "先祖 神话暗金胸甲", "900 物品强度", "鼠标右键"]
    record, _ = _read(harness, {1: lines, 2: lines}, expected_occupied=True, frame_start=-len(lines))
    assert (record.status, record.truncated, record.raw_tts) == ("unparsed", True, lines)
    assert [event["attempt"] for event in record.raw_events] == [1] * 4 + [2] * 4


def test_sigil_title_is_restored_by_the_reader_without_changing_parser_input(harness) -> None:
    record, _ = _read(harness, {1: SIGIL}, expected_occupied=True, frame_start=1)
    assert record.raw_tts == SIGIL
    assert record.normalized_tts == SIGIL[1:]
    assert record.parsed is not None
    assert record.parsed["original_name"] == "梦魇符印"
    assert record.observed_fields is not None
    assert (record.observed_fields["name_text"], record.observed_fields["type_text"]) == (
        "耳语密窟梦魇符印",
        "梦魇符印",
    )


@pytest.mark.parametrize("preamble", [["头部"], ["头部", "电池充电中"]])
def test_partial_slot_label_preamble_of_a_real_item_is_never_a_confirmed_empty_slot(harness, preamble) -> None:
    # Live order before a real equipped item: slot label, "已装备" (equipped), then the item frame. A delivery
    # cut after the label is indistinguishable from an empty-slot announcement, so it must stay unknown.
    head = ("equipped", "equipment", "head")
    record, hovers = _read(harness, {1: preamble, 2: preamble}, expected_occupied=None, where=head)
    assert (record.status, record.attempts, len(hovers)) == ("unverified", 2, 2)
    assert "does not prove the slot empty" in (record.error or "")
    assert [event["text"] for event in record.raw_events] == preamble * 2
    genuine, _ = _read(harness, {1: ["头部", "已装备"]}, expected_occupied=None, where=head)
    assert (genuine.status, genuine.capture_complete, genuine.raw_tts) == ("unparsed", False, ["头部", "已装备"])
