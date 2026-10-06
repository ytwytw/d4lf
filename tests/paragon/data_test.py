from src.paragon import NODES_LEN
from src.paragon.overlay import format_board_display_text
from src.profiles import ParagonBoardModel
from src.settings import get_settings


def test_data_formats_a_board_for_the_overlay(monkeypatch) -> None:
    monkeypatch.setattr(get_settings().general, "language", "enUS")
    board = ParagonBoardModel(
        name="barbarian-starting-board", glyph="hemorrhage", rotation="0°", nodes=[False] * NODES_LEN
    )

    assert format_board_display_text(board) == "Barbarian - Start - Hemorrhage - 0°"
