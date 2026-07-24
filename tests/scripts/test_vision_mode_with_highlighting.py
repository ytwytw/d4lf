import threading
from threading import Event
from types import SimpleNamespace

import numpy as np

import src.scripts.vision_mode_with_highlighting as vision
from src.item.data.rarity import ItemRarity


def _vision_mode_class():
    closure = getattr(vision.VisionModeWithHighlighting, "__closure__", None)
    assert closure is not None
    return next(cell.cell_contents for cell in closure if isinstance(cell.cell_contents, type))


def test_location_retries_parse_each_fresh_crop_including_the_fourth(monkeypatch) -> None:
    frames = [np.full((20, 30, 3), index, dtype=np.uint8) for index in range(4)]
    crops = [np.full((10, 15, 3), index, dtype=np.uint8) for index in range(4)]
    fresh_frames = iter(frames[1:])
    grab_calls = []

    class FakeCam:
        def grab(self, force_new=False):
            grab_calls.append(force_new)
            return next(fresh_frames)

    monkeypatch.setattr(vision, "Cam", FakeCam)
    monkeypatch.setattr(vision.time, "sleep", lambda _seconds: None)

    def find_legendary(frame, _center, expected_rarity=None):
        assert expected_rarity == ItemRarity.Legendary
        return (True, ItemRarity.Legendary, crops[int(frame[0, 0, 0])], (int(frame[0, 0, 0]), 2, 15, 10))

    monkeypatch.setattr(vision, "find_descr", find_legendary)
    expected_item = SimpleNamespace(name="parsed")
    parsed_crops = []

    def fake_read(crop):
        parsed_crops.append(int(crop[0, 0, 0]))
        return expected_item if len(parsed_crops) == 4 else None

    monkeypatch.setattr(vision.src.item.descr.read_descr_tts, "read_descr_mixed", fake_read)

    result = vision._read_item_locations_with_retries(
        initial_frame=frames[0],
        initial_crop=crops[0],
        initial_item_roi=(0, 2, 15, 10),
        item_center=(100, 100),
        expected_rarity=ItemRarity.Legendary,
        cancel_event=Event(),
        max_attempts=4,
    )

    assert result.item is expected_item
    assert parsed_crops == [0, 1, 2, 3]
    assert grab_calls == [True, True, True]
    assert result.item_roi == (3, 2, 15, 10)


def test_location_retries_retain_last_valid_context_when_detection_disappears(monkeypatch) -> None:
    initial_frame = np.full((20, 30, 3), 7, dtype=np.uint8)
    initial_crop = np.full((10, 15, 3), 8, dtype=np.uint8)

    class FakeCam:
        def grab(self, force_new=False):
            assert force_new
            return np.zeros((20, 30, 3), dtype=np.uint8)

    monkeypatch.setattr(vision, "Cam", FakeCam)
    monkeypatch.setattr(vision.time, "sleep", lambda _seconds: None)

    def missing_descr(_frame, _center, expected_rarity=None):
        assert expected_rarity == ItemRarity.Legendary
        return False, None, None, None

    monkeypatch.setattr(vision, "find_descr", missing_descr)

    def fail_parse(_crop):
        message = "missing bullets"
        raise IndexError(message)

    monkeypatch.setattr(vision.src.item.descr.read_descr_tts, "read_descr_mixed", fail_parse)

    result = vision._read_item_locations_with_retries(
        initial_frame=initial_frame,
        initial_crop=initial_crop,
        initial_item_roi=(1, 2, 15, 10),
        item_center=(100, 100),
        expected_rarity=ItemRarity.Legendary,
        cancel_event=Event(),
        max_attempts=3,
    )

    assert result.item is None
    assert isinstance(result.error, IndexError)
    assert result.frame is initial_frame
    assert result.crop is initial_crop
    assert result.item_roi == (1, 2, 15, 10)


def test_highlighting_parse_failure_cancels_previous_worker_and_clears_item(monkeypatch) -> None:
    mode_class = _vision_mode_class()
    mode = object.__new__(mode_class)
    mode._worker_lock = threading.RLock()
    mode.is_running = True
    mode.current_item = object()
    cancel_event = Event()
    clear_requests = []

    class FinishedThread:
        joined = False

        def join(self):
            self.joined = True

    previous_thread = FinishedThread()
    mode.evaluate_item_thread = previous_thread
    mode.evaluate_item_thread_cancel_event = cancel_event
    mode.request_clear = lambda: clear_requests.append(True)

    monkeypatch.setattr(vision, "Cam", lambda: SimpleNamespace(grab=lambda: np.zeros((10, 10, 3), dtype=np.uint8)))
    monkeypatch.setattr(vision.src.tts, "raw_trace_for", lambda trace: trace.copy())
    monkeypatch.setattr(vision.src.tts, "is_equipment_trace", lambda _trace: False)
    monkeypatch.setattr(vision.src.item.descr.read_descr_tts, "read_descr", lambda: None)

    mode.on_tts(["unparsed item"])

    assert cancel_event.is_set()
    assert previous_thread.joined
    assert mode.evaluate_item_thread is None
    assert mode.current_item is None
    assert clear_requests == [True]


def test_highlighting_callback_contains_unexpected_errors() -> None:
    mode_class = _vision_mode_class()
    mode = object.__new__(mode_class)
    mode._worker_lock = threading.RLock()
    mode.is_running = True
    mode.current_item = object()
    clear_requests = []
    mode.request_clear = lambda: clear_requests.append(True)

    def fail(_trace):
        msg = "unexpected callback failure"
        raise RuntimeError(msg)

    mode._handle_tts = fail

    mode.on_tts(["item"])

    assert mode.current_item is None
    assert clear_requests == [True]


def test_stop_thread_and_wait_accepts_a_worker_that_already_cleared_itself() -> None:
    _vision_mode_class().stop_thread_and_wait(None, Event())


def test_highlighting_captures_equipment_when_tooltip_cannot_be_found(monkeypatch) -> None:
    mode = object.__new__(_vision_mode_class())
    mode.is_cleared = True
    mode.clear_when_item_not_selected_thread = None
    mode.clear_when_item_not_selected_thread_cancel_event = None
    mode.evaluate_item_thread = None
    mode.evaluate_item_thread_cancel_event = Event()
    mode.possible_centers = np.array([[10, 10]])
    mode.possible_vendor_centers = mode.possible_centers
    item = SimpleNamespace(
        is_in_shop=False, original_name="magic staff", rarity=ItemRarity.Magic, seasonal_attribute=None
    )
    mode.current_item = item
    clear_requests = []
    mode.request_clear = lambda: clear_requests.append(True)

    frame = np.zeros((20, 30, 3), dtype=np.uint8)

    class FakeCam:
        @staticmethod
        def monitor_to_window(position):
            return position

        @staticmethod
        def grab(force_new=False):
            assert force_new
            return frame

    captures = []
    find_calls = []
    monkeypatch.setattr(vision, "Cam", FakeCam)
    monkeypatch.setattr(vision, "Mouse", SimpleNamespace(get_position=lambda: (10, 10)))
    monkeypatch.setattr(vision, "is_ignored_item", lambda _item: False)
    monkeypatch.setattr(vision.time, "sleep", lambda _seconds: None)

    def missing_tooltip(_frame, _center, expected_rarity=None):
        find_calls.append(expected_rarity)
        return False, None, None, None

    monkeypatch.setattr(vision, "find_descr", missing_tooltip)
    monkeypatch.setattr(vision, "capture_failure", lambda **kwargs: captures.append(kwargs))

    mode.evaluate_item_and_queue_draw(item, Event(), ["framed"], ["raw"])

    assert find_calls == [ItemRarity.Magic] * 5
    assert clear_requests == [True] * 5
    assert len(captures) == 1
    assert captures[0]["reason"] == "visual-tooltip-not-found"
    assert captures[0]["image"] is frame
    assert captures[0]["tts_lines"] == ["framed"]


def test_highlighting_falls_back_to_tts_filter_result_when_locations_fail(monkeypatch) -> None:
    mode = object.__new__(_vision_mode_class())
    mode.is_cleared = True
    mode.clear_when_item_not_selected_thread = None
    mode.clear_when_item_not_selected_thread_cancel_event = None
    mode.evaluate_item_thread = None
    mode.evaluate_item_thread_cancel_event = Event()
    mode.possible_centers = np.array([[10, 10]])
    mode.possible_vendor_centers = mode.possible_centers
    item = SimpleNamespace(
        is_in_shop=False,
        item_type=object(),
        original_name="legendary sword",
        rarity=ItemRarity.Legendary,
        seasonal_attribute=None,
    )
    mode.current_item = item
    mode.request_clear = lambda: None
    mode.request_empty_outline = lambda *_args, **_kwargs: None

    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    crop = np.zeros((10, 15, 3), dtype=np.uint8)
    item_roi = (1, 2, 15, 10)

    class FakeCam:
        @staticmethod
        def monitor_to_window(position):
            return position

        @staticmethod
        def grab(force_new=False):
            assert force_new
            return frame

    monkeypatch.setattr(vision, "Cam", FakeCam)
    monkeypatch.setattr(vision, "Mouse", SimpleNamespace(get_position=lambda: (10, 10)))
    monkeypatch.setattr(vision, "is_ignored_item", lambda _item: False)
    monkeypatch.setattr(vision, "find_descr", lambda *_args, **_kwargs: (True, item.rarity, crop, item_roi))
    monkeypatch.setattr(vision, "compare_histograms", lambda *_args: 1.0)
    monkeypatch.setattr(vision, "is_sigil", lambda _item_type: False)
    monkeypatch.setattr(
        vision,
        "_read_item_locations_with_retries",
        lambda **_kwargs: vision.LocationParseResult(
            item=None, frame=frame, crop=crop, item_roi=item_roi, error=IndexError("missing bullets")
        ),
    )

    filtered_items = []

    class FakeFilter:
        @staticmethod
        def should_keep(filtered_item):
            filtered_items.append(filtered_item)
            return SimpleNamespace(keep=False, matched=[])

    captures = []
    no_match_requests = []
    monitor_requests = []
    monkeypatch.setattr(vision, "Filter", FakeFilter)
    monkeypatch.setattr(vision, "capture_failure", lambda **kwargs: captures.append(kwargs))
    mode.request_no_match_box = lambda requested_item, roi: no_match_requests.append((requested_item, roi))
    mode._start_selection_monitor = lambda center: monitor_requests.append(tuple(center))

    mode.evaluate_item_and_queue_draw(item, Event(), ["framed"], ["raw"])

    assert filtered_items == [item]
    assert no_match_requests == [(item, item_roi)]
    assert monitor_requests == [(10, 10)]
    assert len(captures) == 1
    assert captures[0]["reason"] == "visual-item-parse-failed"
