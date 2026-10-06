import json
from operator import itemgetter
from pathlib import Path

import pytest

from src.inventory_dump.framing import extract_literal_trace
from src.inventory_dump.observations import observe_item_fields
from src.perception import RawTtsEvent

_FIXTURES = json.loads((Path(__file__).parent / "data" / "rune_events.json").read_text(encoding="utf-8"))
_SEASONAL = json.loads((Path(__file__).parent / "data" / "seasonal_item_events.json").read_text(encoding="utf-8"))
_CATEGORIES = json.loads(
    (Path(__file__).parent / "data" / "inventory_category_events.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", _FIXTURES, ids=itemgetter("slot"))
def test_actual_new_rune_headers_preserve_name_type_quantity_and_footer(case) -> None:
    events = [RawTtsEvent(event["sequence"], event["text"], event["received_at"]) for event in case["events"]]
    trace = extract_literal_trace(events)
    assert trace is not None
    assert trace[0] == events[0]
    assert trace[1] == events[1]
    assert trace[-1].text == "鼠标右键"
    observed = observe_item_fields([event.text for event in trace])
    assert observed["quantity"] in {5, 10}
    assert observed["name_text"] == events[0].text


@pytest.mark.parametrize(
    "lines",
    [
        ["安姆 (5)", "暗金仪祭符文", "获得：4 份供品"],
        ["暗金仪祭符文", "获得：4 份供品", "鼠标右键"],
        ["Höpe | 70 (133)", "暗金仪祭符文", "鼠标右键"],
        ["文字说明", "与一枚祈告符文共同插入装备", "鼠标右键"],
    ],
)
def test_rune_framing_requires_exact_header_name_and_observed_footer(lines) -> None:
    assert extract_literal_trace([RawTtsEvent(index, line, 1.0) for index, line in enumerate(lines)]) is None


@pytest.mark.parametrize("case", _SEASONAL, ids=itemgetter("slot"))
def test_actual_seasonal_trophy_and_soul_shard_text_preserves_complete_frame_and_stack(case) -> None:
    events = [RawTtsEvent(event["sequence"], event["text"], event["received_at"]) for event in case["events"]]
    trace = extract_literal_trace(events)
    assert trace is not None
    assert trace == events
    assert trace[-1].text == "鼠标右键"
    observed = observe_item_fields([event.text for event in trace])
    assert observed["name_text"] == events[0].text
    assert observed["type_text"] == events[1].text
    assert observed["quantity"] == case["quantity"]
    assert observed["description_lines"] == [event.text for event in trace[2:]]


@pytest.mark.parametrize("header", ["暗金战利品", "传奇灵魂尖刺", "稀有灵魂尖刺", "魔法灵魂尖刺"])
def test_seasonal_frame_still_requires_footer_and_rejects_header_as_prose(header) -> None:
    incomplete = [RawTtsEvent(index, text, 1.0) for index, text in enumerate(["新物品 (3)", header, "完整说明"])]
    assert extract_literal_trace(incomplete) is None
    prose = [
        RawTtsEvent(index, text, 1.0) for index, text in enumerate(["物品", "包含" + header + "的说明", "鼠标右键"])
    ]
    assert extract_literal_trace(prose) is None


@pytest.mark.parametrize("case", _CATEGORIES, ids=itemgetter("slot"))
def test_actual_inventory_categories_keep_all_description_until_explicit_footer(case) -> None:
    events = [RawTtsEvent(index, line, 1.0) for index, line in enumerate(case["lines"])]
    footer = case["lines"].index("鼠标右键")
    trace = extract_literal_trace(events)
    assert trace is not None
    assert trace == events[: footer + 1]
    observed = observe_item_fields([event.text for event in trace])
    assert observed["name_text"] == case["name"]
    assert observed["type_text"] == case["header"]
    assert observed["quantity"] == case["quantity"]
    assert observed["description_lines"] == case["lines"][2 : footer + 1]
    # A known title without the explicit footer must remain incomplete.
    assert extract_literal_trace(events[:footer]) is None


@pytest.mark.parametrize("case", _CATEGORIES, ids=itemgetter("slot"))
def test_inventory_category_words_in_prose_or_ui_do_not_frame_an_item(case) -> None:
    lines = ["任务提示", "寻找" + case["header"], "鼠标右键"]
    assert extract_literal_trace([RawTtsEvent(index, text, 1.0) for index, text in enumerate(lines)]) is None
    no_name = [case["header"], "鼠标右键"]
    assert extract_literal_trace([RawTtsEvent(index, text, 1.0) for index, text in enumerate(no_name)]) is None
