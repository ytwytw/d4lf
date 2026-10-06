"""Source-constructed effect examples; these are not live game captures."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog
from src.game_data import catalog as catalog_module
from src.perception import parse_item_text
from src.perception.parser.aspects import _resolve_shared_aspect
from src.perception.parser.details import _get_aspect_from_name

MALICIOUS = "处于恶魔形态时，近距范围内每有一名恶魔或敌人，你造成的伤害就会提高 3.5%，最多提高 70%。"
VIRULENT = (
    "狂犬撕咬感染敌人后，其冷却时间缩短 1.25 秒。当感染对象为精英敌人时，冷却时间缩减变为原来的三倍。"
    "此外，你对受到狂犬撕咬影响的敌人额外造成 20% 增伤伤害。"
)


@pytest.fixture
def chinese_catalog(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", catalog)
    return catalog


@pytest.mark.parametrize(("text", "canonical"), [(MALICIOUS, "malicious"), (VIRULENT, "virulent")])
def test_complete_shared_effect_resolves_only_with_ambiguous_name(chinese_catalog, text, canonical) -> None:
    assert chinese_catalog.resolve_aspect("恶毒之手套") is None
    aspect = _get_aspect_from_name(text, "恶毒之手套")
    assert aspect.name == canonical
    assert aspect.text == text
    assert _resolve_shared_aspect(text, "未知新威能之手套", chinese_catalog) is None


@pytest.mark.parametrize(
    "text",
    [
        MALICIOUS.replace("3.5%", "3.5% [2.5 - 4.5]% [x]"),
        MALICIOUS.replace("3.5%", "[2.5 - 4.5]%[x]"),
        MALICIOUS.replace("3.5%", "x3.5%"),
        MALICIOUS.replace("3.5%", "3.5[2.5-4.5]%"),
        MALICIOUS.replace("3.5%", "３．５％"),
        MALICIOUS.replace("，", ",\n "),
        "已刻印： " + MALICIOUS,
        "刻印: " + MALICIOUS,
    ],
)
def test_effect_allows_numeric_markers_ranges_and_whitespace(chinese_catalog, text) -> None:
    assert _resolve_shared_aspect(text, "恶毒之手套", chinese_catalog) == "malicious"


def test_cooldown_roll_and_damage_range_keep_the_complete_virulent_structure(chinese_catalog) -> None:
    text = VIRULENT.replace("1.25", "1.25 [1.00 - 2.00]").replace("20%", "20% [10 - 30]%[x]")
    assert _resolve_shared_aspect(text, "恶毒之手套", chinese_catalog) == "virulent"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "恶毒",
        "恶魔 狂犬撕咬",
        MALICIOUS.split("，最多", maxsplit=1)[0],
        VIRULENT.split("此外", maxsplit=1)[0],
        MALICIOUS + VIRULENT,
        VIRULENT + "\n" + MALICIOUS,
        MALICIOUS.replace("恶魔或敌人", "恶魔"),
        MALICIOUS.replace("3.5", "#"),
        VIRULENT.replace("三倍", "两倍"),
        "未知附加效果。" + MALICIOUS,
        MALICIOUS + "未知附加效果。",
    ],
)
def test_unknown_truncated_or_conflicting_effect_fails_closed(chinese_catalog, text) -> None:
    with pytest.raises(ValueError, match="legendary aspect"):
        _get_aspect_from_name(text, "恶毒之手套")


@pytest.mark.parametrize("canonical", ["malicious", "virulent"])
def test_english_canonical_names_keep_existing_resolution(chinese_catalog, canonical) -> None:
    assert _get_aspect_from_name("Existing named-aspect path", canonical).name == canonical


@pytest.mark.parametrize("change", ["missing_identity", "third_identity", "longer_label"])
def test_effect_does_not_resolve_a_different_name_candidate_set(chinese_catalog, monkeypatch, change) -> None:
    labels = dict(chinese_catalog.aspect_dict)
    if change == "missing_identity":
        labels.pop("virulent")
    elif change == "third_identity":
        labels["unknown_aspect"] = "恶毒"
    else:
        labels["unknown_aspect"] = "恶毒之手套"
    monkeypatch.setattr(chinese_catalog, "aspect_dict", labels)
    assert _resolve_shared_aspect(MALICIOUS, "恶毒之手套", chinese_catalog) is None


def test_chinese_effect_does_not_override_another_locale(chinese_catalog, monkeypatch) -> None:
    monkeypatch.setattr(chinese_catalog, "grammar", replace(chinese_catalog.grammar, locale="enUS"))
    assert _resolve_shared_aspect(MALICIOUS, "恶毒之手套", chinese_catalog) is None


def _tooltip(effect: str) -> list[str]:
    return [
        "恶毒之手套",
        "传奇手套",
        "838 物品强度",
        "1,000 护甲值",
        "+69 点意力 +[69 - 83]",
        "+746 生命上限 [741 - 1,000]",
        "+810 荆棘 [576 - 865]",
        "+1,723 点火焰抗性 [1,600 - 1,799]",
        effect,
        "需要等级: 67",
        "鼠标右键",
    ]


@pytest.mark.parametrize(("text", "canonical"), [(MALICIOUS, "malicious"), (VIRULENT, "virulent")])
def test_current_tooltip_effect_is_used_by_item_parser(chinese_catalog, text, canonical) -> None:
    item = parse_item_text(_tooltip(text))
    assert item is not None
    assert item.aspect is not None
    assert item.aspect.name == canonical
    assert item.aspect.text == text


def test_parser_never_borrows_another_tooltip_or_prior_effect(chinese_catalog) -> None:
    for effect in (MALICIOUS, VIRULENT):
        assert parse_item_text(_tooltip(effect)) is not None
        with pytest.raises(ValueError, match="legendary aspect"):
            parse_item_text(_tooltip("未知或截断效果") + _tooltip(effect))


def test_parser_rejects_both_effects_in_one_tooltip(chinese_catalog) -> None:
    with pytest.raises(ValueError, match="legendary aspect"):
        parse_item_text(_tooltip(MALICIOUS + VIRULENT))


@pytest.mark.parametrize(("first", "second"), [(MALICIOUS, VIRULENT), (VIRULENT, MALICIOUS)])
def test_parser_rejects_conflicting_effects_on_separate_current_tooltip_lines(chinese_catalog, first, second) -> None:
    trace = _tooltip(first)
    trace.insert(9, second)
    original = list(trace)
    with pytest.raises(ValueError, match="Conflicting legendary aspect"):
        parse_item_text(trace)
    assert trace == original


@pytest.mark.parametrize(
    ("first", "second", "canonical"), [(MALICIOUS, VIRULENT, "malicious"), (VIRULENT, MALICIOUS, "virulent")]
)
def test_parser_does_not_treat_next_tooltip_as_a_current_effect_conflict(
    chinese_catalog, first, second, canonical
) -> None:
    item = parse_item_text(_tooltip(first) + _tooltip(second))
    assert item is not None
    assert item.aspect is not None
    assert item.aspect.name == canonical
