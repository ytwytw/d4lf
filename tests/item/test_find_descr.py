from types import SimpleNamespace

import numpy as np

import src.item.find_descr as find_descr_module
from src.config.ui import ResManager
from src.item.data.rarity import ItemRarity
from src.template_finder import SearchResult, TemplateMatch


def _match(
    center: tuple[int, int], *, name: str = "", region: list[int] | None = None, score: float = -1.0
) -> TemplateMatch:
    match_region = region or [center[0], center[1], 1, 1]
    return TemplateMatch(
        center=center,
        center_monitor=center,
        name=name,
        region=match_region,
        region_monitor=match_region.copy(),
        score=score,
    )


def test_find_descr_uses_lowest_bottom_edge_instead_of_highest_score(monkeypatch) -> None:
    previous_resolution = "x".join(str(value) for value in ResManager().resolution)
    ResManager().set_resolution("1920x1080")
    try:
        top_left = _match(center=(505, 105), name="item_leg_top_left", region=[500, 100, 10, 10], score=0.95)
        top_searches = iter([SearchResult(matches=[top_left], success=True), SearchResult(success=False)])
        monkeypatch.setattr(find_descr_module, "_template_search", lambda *_args, **_kwargs: next(top_searches))

        high_score_separator = _match(center=(700, 350), name="item_bottom_edge", score=0.95)
        actual_bottom_edge = _match(center=(700, 900), name="item_bottom_edge", score=0.70)

        def fake_search(ref, *_args, **_kwargs):
            if ref == ["item_bottom_edge"]:
                return SearchResult(matches=[high_score_separator, actual_bottom_edge], success=True)
            return SearchResult(matches=[_match(center=(650, 200), score=0.90)], success=True)

        monkeypatch.setattr(find_descr_module, "search", fake_search)

        found, rarity, crop, roi = find_descr_module.find_descr(np.zeros((1080, 1920, 3), dtype=np.uint8), (960, 540))

        assert found
        assert rarity == ItemRarity.Legendary
        assert roi == (515, 115, 360, 748)
        assert crop is not None
        assert crop.shape == (748, 360, 3)
    finally:
        ResManager().set_resolution(previous_resolution)


def test_find_descr_uses_separator_fallback_when_rarity_is_known(monkeypatch) -> None:
    previous_resolution = "x".join(str(value) for value in ResManager().resolution)
    ResManager().set_resolution("1920x1080")
    try:
        separator = _match(
            center=(1105, 305), name="item_seperator_short_rare", region=[1015, 300, 179, 11], score=0.97
        )
        bottom_edge = _match(center=(1200, 900), name="item_bottom_edge", score=0.70)

        def fake_search(ref, *_args, **_kwargs):
            if ref == ["item_bottom_edge"]:
                return SearchResult(matches=[bottom_edge], success=True)
            return SearchResult(matches=[separator], success=True)

        monkeypatch.setattr(find_descr_module, "search", fake_search)

        found, rarity, crop, roi = find_descr_module.find_descr(
            np.zeros((1080, 1920, 3), dtype=np.uint8), (960, 540), expected_rarity=ItemRarity.Magic
        )

        assert found
        assert rarity == ItemRarity.Magic
        assert roi == (1015, 165, 360, 698)
        assert crop is not None
        assert crop.shape == (698, 360, 3)
    finally:
        ResManager().set_resolution(previous_resolution)


def test_find_descr_accepts_tooltip_shifted_by_left_panel_edge(monkeypatch) -> None:
    previous_resolution = "x".join(str(value) for value in ResManager().resolution)
    ResManager().set_resolution("1920x1080")
    try:
        separator = _match(
            center=(1240, 305), name="item_seperator_short_rare", region=[1150, 300, 179, 11], score=0.97
        )
        bottom_edge = _match(center=(1300, 900), name="item_bottom_edge", score=0.70)

        def fake_search(ref, *_args, **_kwargs):
            if ref == ["item_bottom_edge"]:
                return SearchResult(matches=[bottom_edge], success=True)
            return SearchResult(matches=[separator], success=True)

        monkeypatch.setattr(find_descr_module, "search", fake_search)

        found, rarity, crop, roi = find_descr_module.find_descr(
            np.zeros((1080, 1920, 3), dtype=np.uint8), (960, 540), expected_rarity=ItemRarity.Unique
        )

        assert found
        assert rarity == ItemRarity.Unique
        assert roi == (1150, 165, 360, 698)
        assert crop is not None
    finally:
        ResManager().set_resolution(previous_resolution)


def test_find_descr_separator_fallback_rejects_matches_far_from_tooltip_edge(monkeypatch) -> None:
    previous_resolution = "x".join(str(value) for value in ResManager().resolution)
    ResManager().set_resolution("1920x1080")
    try:
        distant_separator = _match(
            center=(1290, 305), name="item_seperator_short_rare", region=[1200, 300, 179, 11], score=0.97
        )
        monkeypatch.setattr(
            find_descr_module,
            "search",
            lambda *_args, **_kwargs: SearchResult(matches=[distant_separator], success=True),
        )
        monkeypatch.setattr(
            find_descr_module, "_template_search", lambda *_args, **_kwargs: SearchResult(success=False)
        )

        found, rarity, crop, roi = find_descr_module.find_descr(
            np.zeros((1080, 1920, 3), dtype=np.uint8), (960, 540), expected_rarity=ItemRarity.Rare
        )

        assert not found
        assert rarity is None
        assert crop is None
        assert roi is None
    finally:
        ResManager().set_resolution(previous_resolution)


def test_find_descr_ignores_successful_search_without_matches(monkeypatch) -> None:
    resources = SimpleNamespace(
        offsets=SimpleNamespace(item_descr_width=100, item_descr_pad=10),
        pos=SimpleNamespace(window_dimensions=(3840, 2160)),
        roi=SimpleNamespace(
            rel_descr_search_left=np.array([0, 0, 10, 10]), rel_descr_search_right=np.array([0, 0, 10, 10])
        ),
    )
    search_results = iter([SearchResult(success=True), SearchResult()])
    monkeypatch.setattr(find_descr_module, "ResManager", lambda: resources)
    monkeypatch.setattr(find_descr_module, "_template_search", lambda *_args, **_kwargs: next(search_results))

    assert find_descr_module.find_descr(np.zeros((20, 20, 3), dtype=np.uint8), (0, 0)) == (False, None, None, None)
