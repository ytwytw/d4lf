from src.locale_data import LocaleGrammar
from src.perception.framing import TtsFramer, find_item_start, fix_data


class _Catalog:
    def __init__(self, item_types: dict[str, str]):
        self.item_types = item_types

    def resolve_item_type(self, value: str) -> str | None:
        return self.item_types.get(value)


def test_find_item_start_uses_localized_header() -> None:
    grammar = LocaleGrammar.from_dict(
        "zhCN", {"labels": {"ancestral": ["先祖"], "item_start_ignored": ["词缀"]}, "rarities": {"Unique": ["暗金"]}}
    )
    catalog = _Catalog({"双手剑": "Sword2H"})
    trace = ["无关界面文字", "祖父", "先祖暗金双手剑", "925 物品强度"]

    assert find_item_start(trace, grammar=grammar, catalog=catalog) == 1


def test_find_item_start_accepts_localized_tribute_and_compass_suffixes() -> None:
    grammar = LocaleGrammar.from_dict(
        "zhCN",
        {
            "identifiers": {"COMPASS": ["罗盘"], "TRIBUTE": ["贡品", "供品"]},
            "labels": {"item_start_ignored": ["罗盘词缀"]},
        },
    )
    catalog = _Catalog({})

    assert find_item_start(["无关文字", "和谐供品"], grammar=grammar, catalog=catalog) == 1
    assert find_item_start(["无关文字", "炼狱罗盘"], grammar=grammar, catalog=catalog) == 1
    assert find_item_start(["无关文字", "罗盘词缀"], grammar=grammar, catalog=catalog) is None


def test_localized_tribute_metadata_does_not_replace_item_name() -> None:
    grammar = LocaleGrammar.from_dict("zhCN", {"identifiers": {"TRIBUTE": ["贡品"]}, "rarities": {"Rare": ["稀有"]}})
    trace = ["无关文字", "巨人贡品 (4)", "稀有巨人贡品", "鼠标右键"]

    assert find_item_start(trace, grammar=grammar, catalog=_Catalog({})) == 1


def test_tts_framer_emits_localized_trace_and_bounds_noise() -> None:
    grammar = LocaleGrammar.from_dict(
        "zhCN",
        {
            "labels": {"item_end_control": ["鼠标左键"], "item_start_ignored": ["词缀"]},
            "rarities": {"Legendary": ["传奇"]},
        },
    )
    catalog = _Catalog({"戒指": "Ring"})
    framer = TtsFramer(grammar, catalog, max_lines=5)

    for index in range(20):
        assert framer.feed(f"噪声{index}") is None
        assert len(framer.lines) <= 5
    assert framer.lines == ["噪声15", "噪声16", "噪声17", "噪声18", "噪声19"]
    assert framer.feed("测试之戒") is None
    assert framer.feed("传奇戒指") is None
    assert framer.feed("鼠标左键") == ["测试之戒", "传奇戒指", "鼠标左键"]


def test_tts_framer_keeps_raw_lines() -> None:
    grammar = LocaleGrammar.from_dict(
        "enUS", {"labels": {"item_end_control": ["Right mouse button"]}, "rarities": {"Legendary": ["Legendary"]}}
    )
    catalog = _Catalog({"ring": "Ring"})
    framer = TtsFramer(grammar, catalog)

    assert framer.feed("TEST ITEM", raw_data="[FAVORITED ITEM]. TEST ITEM") is None
    assert framer.feed("Legendary Ring", raw_data="Legendary Ring") is None
    assert framer.feed("Right mouse button", raw_data="Right mouse button") == [
        "TEST ITEM",
        "Legendary Ring",
        "Right mouse button",
    ]
    assert framer.last_raw_item == ["[FAVORITED ITEM]. TEST ITEM", "Legendary Ring", "Right mouse button"]


def test_tts_framer_rejects_category_without_rarity_or_item_power() -> None:
    grammar = LocaleGrammar.from_dict(
        "zhCN", {"labels": {"item_end_control": ["鼠标右键"], "item_power": ["物品强度"]}, "rarities": {}}
    )
    catalog = _Catalog({"戒指": "Ring"})
    framer = TtsFramer(grammar, catalog)

    for line in ["戒指", "戒指", "费用：50 古币", "鼠标右键"]:
        assert framer.feed(line) is None

    framer = TtsFramer(grammar, catalog)
    for line in ["朴素戒指", "戒指", "850 物品强度"]:
        assert framer.feed(line) is None
    assert framer.feed("鼠标右键") == ["朴素戒指", "戒指", "850 物品强度", "鼠标右键"]


def test_fix_data_removes_english_and_localized_item_prefixes() -> None:
    grammar = LocaleGrammar.from_dict("zhCN", {"labels": {"item_name_prefix": ["[收藏物品]."]}})

    assert fix_data("[收藏物品]. 无限法衣", grammar=grammar) == "无限法衣"
    assert fix_data("[MARKED AS JUNK]. [FAVORITED ITEM]. Name", grammar=grammar) == "Name"


def test_trace_remembers_actual_first_raw_sequence_not_only_completion() -> None:
    grammar = LocaleGrammar.from_dict("enUS", {"labels": {"item_end_control": ["Right mouse button"]}})
    framer = TtsFramer(grammar, _Catalog({}))
    framer.feed("unrelated", raw_sequence=5)
    framer.feed("TEST ITEM", raw_sequence=8)
    assert framer.feed("Right mouse button", raw_sequence=12) == ["TEST ITEM", "Right mouse button"]
    assert framer.last_raw_start_sequence == 8
    assert not framer.last_item_truncated


def test_framer_exposes_overflow_instead_of_claiming_complete_text() -> None:
    grammar = LocaleGrammar.from_dict("enUS", {"labels": {"item_end_control": ["Right mouse button"]}})
    framer = TtsFramer(grammar, _Catalog({}), max_lines=3)
    framer.feed("ITEM", raw_sequence=1)
    framer.feed("first line", raw_sequence=2)
    framer.feed("UNEXPECTED HEADER", raw_sequence=3)
    framer.feed("last line", raw_sequence=4)
    assert framer.feed("Right mouse button", raw_sequence=5)
    assert framer.last_item_truncated
    assert framer.last_raw_start_sequence == 3
