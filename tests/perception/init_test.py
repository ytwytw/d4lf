import sys

import pytest

from src import perception
from src.game_data import ItemType
from src.item import Item


def test_perception_facade_exposes_typed_item_and_geometry_operations() -> None:
    item = perception.parse_item_text(["MALIGNANT HEART", "Legendary Boss Key"])

    assert item is not None
    assert item.original_name == "MALIGNANT HEART"
    assert perception.get_center((0, 0, 10, 10)) == (5, 5)


def test_parse_item_text_is_typed_facade_for_terminal_items() -> None:
    item = perception.parse_item_text(["MALIGNANT HEART", "Legendary Boss Key"])

    assert item is not None
    assert item.item_type == ItemType.LairBossKey


def test_capture_is_the_callable_public_facade() -> None:
    assert callable(perception.capture)


def test_only_completed_items_newer_than_hover_are_parsed(monkeypatch, mocker) -> None:
    item = Item()
    parse = mocker.Mock(return_value=item)
    monkeypatch.setattr(perception, "parse_item_text", parse)
    monkeypatch.setattr(perception._listener, "get_latest_item_snapshot", lambda: (8, ["item"]))

    assert perception.latest_item_sequence() == 8
    assert perception.read_latest_item(after_sequence=8) is None
    assert perception.read_latest_item(after_sequence=9) is None
    parse.assert_not_called()
    assert perception.read_latest_item(after_sequence=7) is item
    parse.assert_called_once_with(["item"])
    assert perception.read_latest_item() is item


@pytest.mark.skipif(sys.platform == "win32", reason="No-op adapter is selected on non-Windows only")
def test_start_connection_is_safe_without_windows_tts() -> None:
    perception.start_connection()

    assert perception.is_connected() is False
