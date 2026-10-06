"""Source-constructed tribute descriptions; no live Titans or Heritage sample is claimed."""

from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog, ItemRarity
from src.game_data import catalog as catalog_module
from src.perception import parse_item_text
from src.perception.parser.tributes import _resolve_tribute_from_tts

HERITAGE = (
    "所有难度均可使用。\n\n向幽暗之城中的灵焰火盆进献贡品，以此来丰富地下城奖励。\n"
    "如果在完成地下城时至少达到了调谐级别 1，则可获得职业专属的暗金物品。"
)
TITANS = "向幽暗之城中的灵焰火盆进献贡品来丰富奖励：\n达到调谐级别 1 可获得巢穴首领秘宝钥匙。\n\n仅在折磨难度可用。"


@pytest.fixture
def chinese_catalog(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", catalog)
    return catalog


def _tooltip(description: str, rarity: str = "稀有") -> list[str]:
    return ["巨人贡品 (4)", rarity + "巨人贡品", description, "出售价格: 1 金币", "鼠标右键"]


@pytest.mark.parametrize(
    ("description", "canonical"), [(HERITAGE, "tribute_of_heritage"), (TITANS, "tribute_of_titans")]
)
@pytest.mark.parametrize(("rarity", "expected"), [("魔法", ItemRarity.Magic), ("稀有", ItemRarity.Rare)])
def test_shared_tribute_uses_complete_description_not_rarity(
    chinese_catalog, description, canonical, rarity, expected
) -> None:
    trace = _tooltip(description, rarity)
    original = list(trace)
    item = parse_item_text(trace)
    assert item is not None
    assert item.name == canonical
    assert item.rarity is expected
    assert trace == original


def test_name_only_catalog_still_refuses_shared_tribute(chinese_catalog) -> None:
    assert chinese_catalog.resolve_tribute("巨人贡品") is None


@pytest.mark.parametrize(
    "description",
    [
        "",
        "巢穴首领秘宝钥匙",
        "职业专属的暗金物品",
        TITANS.split("仅在", maxsplit=1)[0],
        HERITAGE.split("如果", maxsplit=1)[0],
        HERITAGE + TITANS,
        TITANS + HERITAGE,
        TITANS.replace("级别 1", "级别 2"),
        TITANS.replace("巢穴首领秘宝钥匙", "暗金物品"),
        TITANS + "未知额外奖励。",
    ],
)
def test_unknown_truncated_or_mixed_tribute_fails_closed(chinese_catalog, description) -> None:
    trace = _tooltip(description)
    original = list(trace)
    with pytest.raises(ValueError, match="tribute name"):
        parse_item_text(trace)
    assert trace == original


@pytest.mark.parametrize("description", [HERITAGE, TITANS])
def test_description_allows_tts_paragraph_separators_and_spacing(chinese_catalog, description) -> None:
    normalized = description.replace("：\n", "：. ").replace("。\n", "。. ")
    assert parse_item_text(_tooltip(normalized)) is not None


def test_shared_name_without_description_is_rejected(chinese_catalog) -> None:
    with pytest.raises(ValueError, match="tribute name"):
        parse_item_text(["巨人贡品 (4)", "稀有巨人贡品"])


def test_unknown_name_cannot_borrow_a_matching_effect(chinese_catalog) -> None:
    with pytest.raises(ValueError, match="tribute name"):
        parse_item_text(["未知贡品", "稀有未知贡品", TITANS])


def test_conflicting_name_and_header_are_rejected(chinese_catalog) -> None:
    with pytest.raises(ValueError, match="tribute name"):
        parse_item_text(["巧思贡品", "稀有巨人贡品", TITANS])


def test_extra_complete_effect_before_footer_is_rejected(chinese_catalog) -> None:
    trace = _tooltip(TITANS)
    trace.insert(3, HERITAGE)
    with pytest.raises(ValueError, match="tribute name"):
        parse_item_text(trace)


def test_later_tooltip_and_previous_call_cannot_supply_missing_effect(chinese_catalog) -> None:
    assert parse_item_text(_tooltip(TITANS)) is not None
    with pytest.raises(ValueError, match="tribute name"):
        parse_item_text(_tooltip("未知或截断效果") + _tooltip(TITANS))


def test_later_tooltip_does_not_override_current_complete_identity(chinese_catalog) -> None:
    item = parse_item_text(_tooltip(HERITAGE) + _tooltip(TITANS))
    assert item is not None
    assert item.name == "tribute_of_heritage"


@pytest.mark.parametrize("change", ["third_identity", "missing_identity"])
def test_unexpected_catalog_candidates_are_not_guessed(chinese_catalog, monkeypatch, change) -> None:
    labels = dict(chinese_catalog.tribute_dict)
    if change == "third_identity":
        labels["unknown_tribute"] = "巨人贡品"
    else:
        labels.pop("tribute_of_heritage")
    monkeypatch.setattr(chinese_catalog, "tribute_dict", labels)
    assert _resolve_tribute_from_tts(_tooltip(TITANS), "巨人贡品", chinese_catalog) is None


@pytest.mark.parametrize("name", ["tribute_of_heritage", "tribute_of_titans"])
def test_canonical_names_keep_existing_resolution(chinese_catalog, name) -> None:
    assert _resolve_tribute_from_tts([name, "Rare Tribute"], "Tribute", chinese_catalog) == name
