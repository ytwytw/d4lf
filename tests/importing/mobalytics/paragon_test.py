from typing import cast

import pytest

from src.importing.mobalytics.paragon import extract_mobalytics_paragon_steps


def test_mobalytics_paragon_extractor_returns_empty_for_missing_data() -> None:
    assert extract_mobalytics_paragon_steps({}) == []


@pytest.mark.parametrize("node_prefix", ["rogue-starter-board", "rogue-starting-board"])
def test_mobalytics_starting_board_keeps_node_slug_prefixes(node_prefix: str) -> None:
    steps = extract_mobalytics_paragon_steps({
        "boards": [{"board": {"slug": "rogue-starter-board"}, "glyph": {"slug": "rogue-versatility"}, "rotation": 0}],
        "nodes": [{"slug": f"{node_prefix}-x11-y14"}, {"slug": "rogue-other-board-x12-y14"}],
    })

    board = steps[0][0]
    assert board["Name"] == "rogue-starting-board"
    assert sum(cast("list[bool]", board["Nodes"])) == 1
