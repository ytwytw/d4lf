# ruff: noqa: PLC0415

from types import SimpleNamespace

import pytest

from src.item.data.affix import AffixType
from src.item.data.item_type import ItemType
from src.item.data.rarity import ItemRarity
from src.item.models import Item
from src.locale_data import LocaleGrammar, canonical_text_key, normalize_locale_text


def test_normalize_locale_text_preserves_cjk_and_normalizes_width():
    assert normalize_locale_text("  ＋７９ 点 智力\xa0") == "+79 点 智力"
    assert canonical_text_key("祖父 （暗金）") == "祖父_暗金"


def test_locale_grammar_accepts_adjacent_cjk_rarity_and_type():
    grammar = LocaleGrammar.from_dict("zhCN", {"labels": {"ancestral": ["先祖"]}, "rarities": {"Unique": ["暗金"]}})

    header = grammar.strip_terms("先祖暗金双手剑", "ancestral")
    assert grammar.rarity_name(header) == "Unique"
    assert grammar.strip_rarity(header, "Unique") == "双手剑"


def test_locale_grammar_ignores_blank_terms():
    grammar = LocaleGrammar.from_dict(
        "zhCN",
        {"labels": {"ancestral": ["", "  "]}, "identifiers": {"NIGHTMARE_SIGIL": ""}, "rarities": {"Unique": [""]}},
    )

    assert not grammar.contains("ancestral", "未知物品")
    assert not grammar.identifier_matches("NIGHTMARE_SIGIL", "未知物品")
    assert grammar.rarity_name("未知物品") is None


def test_zhcn_ambiguous_shadow_damage_uses_range_precision_and_fails_closed(monkeypatch):
    import src.item.descr.read_descr_tts as parser
    from src.dataloader import Dataloader

    grammar = LocaleGrammar.from_dict(
        "zhCN", {"affix_range_precision": {"暗影伤害": {"decimal": "shade_damage", "integer": "shadow_damage"}}}
    )
    catalog = object.__new__(Dataloader)
    catalog.grammar = grammar
    catalog.affix_dict = {"shade_damage": "暗影伤害", "shadow_damage": "暗影伤害"}
    catalog.charm_affix_dict = {}
    catalog.seal_affix_dict = {}
    catalog._affix_aliases = Dataloader._alias_index(catalog.affix_dict)
    catalog._charm_affix_aliases = {}
    catalog._seal_affix_aliases = {}
    monkeypatch.setattr(parser, "Dataloader", lambda: catalog)

    shade = parser._get_affix_from_text("30.0% 暗影伤害 [20.0 - 40.0]")
    shadow = parser._get_affix_from_text("30% 暗影伤害 [20 - 40]")

    assert shade.name == "shade_damage"
    assert shadow.name == "shadow_damage"
    assert parser._resolve_affix_name("30% 暗影伤害") is None


def test_declared_aspect_alias_equivalence_resolves_and_matches_all_canonical_ids():
    from src.dataloader import Dataloader

    catalog = object.__new__(Dataloader)
    catalog.grammar = LocaleGrammar.from_dict("zhCN", {"aspect_alias_equivalence": {"恶毒": ["malicious", "virulent"]}})
    catalog.aspect_dict = {"malicious": "恶毒", "virulent": "恶毒"}
    catalog._aspect_aliases = Dataloader._alias_index(catalog.aspect_dict)

    assert catalog.resolve_aspect("恶毒戒指") == "malicious"
    assert catalog.aspect_names_equivalent("malicious", "virulent")
    assert not catalog.aspect_names_equivalent("malicious", "unrelated")


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("+3 最大闪避次数", "maximum_evade_charges"),
        ("攻击使闪避的冷却时间缩短 1.9 秒", "attacks_reduce_evades_cooldown_by_seconds"),
        ("不可摧毁", "indestructible"),
        ("+188% 闪避给予的移动速度，持续 1.5 秒", "evade_grants_movement_speed_for_seconds"),
        ("+132% 闪避给予的移动速度，持续 1.5 秒 [125 - 150]%[1.5]", "evade_grants_movement_speed_for_seconds"),
        ("+30.0% 毒素伤害 [20.0 - 40.0]", "poisoning_damage"),
        ("+30% 毒素伤害 [20 - 40]", "poison_damage"),
    ],
)
def test_zhcn_live_affix_aliases_are_runtime_resolvable(monkeypatch, text, expected_name):
    import src.item.descr.read_descr_tts as parser
    from src.config.loader import IniConfigLoader
    from src.dataloader import Dataloader

    monkeypatch.setattr(IniConfigLoader()._general, "language", "zhCN")
    catalog = object.__new__(Dataloader)
    catalog.load_data()
    monkeypatch.setattr(parser, "Dataloader", lambda: catalog)

    assert parser._get_affix_from_text(text).name == expected_name


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("和谐供品", "tribute_of_harmony"),
        ("光辉贡品（决绝）", "tribute_of_radiance_resolute"),
        ("巨人贡品", "tribute_of_titans"),
    ],
)
def test_zhcn_reviewed_tribute_aliases_are_runtime_resolvable(monkeypatch, text, expected_name):
    from src.config.loader import IniConfigLoader
    from src.dataloader import Dataloader

    monkeypatch.setattr(IniConfigLoader()._general, "language", "zhCN")
    catalog = object.__new__(Dataloader)
    catalog.load_data()

    assert catalog.resolve_tribute(text) == expected_name


def test_find_item_start_uses_localized_header(monkeypatch):
    import src.tts

    grammar = LocaleGrammar.from_dict(
        "zhCN",
        {
            "labels": {"ancestral": ["先祖"], "item_start_ignored": ["词缀"]},
            "identifiers": {},
            "rarities": {"Unique": ["暗金"]},
        },
    )
    catalog = SimpleNamespace(grammar=grammar, resolve_item_type=lambda value: "Sword2H" if value == "双手剑" else None)
    monkeypatch.setattr(src.tts, "Dataloader", lambda: catalog)

    trace = ["无关界面文字", "祖父", "先祖暗金双手剑", "925 物品强度"]
    assert src.tts.find_item_start(trace, grammar=grammar) == 1


def test_tts_framer_emits_localized_trace_and_bounds_noise():
    from src.tts import TtsFramer

    grammar = LocaleGrammar.from_dict(
        "zhCN",
        {
            "labels": {"item_end_control": ["鼠标左键"], "item_start_ignored": ["词缀"]},
            "rarities": {"Legendary": ["传奇"]},
        },
    )
    catalog = SimpleNamespace(resolve_item_type=lambda value: "Ring" if value == "戒指" else None)
    framer = TtsFramer(grammar, catalog, max_lines=5)

    for index in range(20):
        line = f"噪声{index}"
        assert framer.feed(line) is None
        assert len(framer.lines) <= 5
    assert framer.lines == ["噪声15", "噪声16", "噪声17", "噪声18", "噪声19"]
    assert framer.feed("测试之戒") is None
    assert framer.feed("传奇戒指") is None
    assert framer.feed("鼠标左键") == ["测试之戒", "传奇戒指", "鼠标左键"]


def test_tts_framer_keeps_raw_lines_for_failure_capture():
    from src.tts import TtsFramer

    grammar = LocaleGrammar.from_dict(
        "enUS", {"labels": {"item_end_control": ["Right mouse button"]}, "rarities": {"Legendary": ["Legendary"]}}
    )
    catalog = SimpleNamespace(resolve_item_type=lambda value: "Ring" if value == "Ring" else None)
    framer = TtsFramer(grammar, catalog)

    assert framer.feed("TEST ITEM", raw_data="[FAVORITED ITEM]. TEST ITEM") is None
    assert framer.feed("Legendary Ring", raw_data="Legendary Ring") is None
    assert framer.feed("Right mouse button", raw_data="Right mouse button") == [
        "TEST ITEM",
        "Legendary Ring",
        "Right mouse button",
    ]
    assert framer.last_raw_item == ["[FAVORITED ITEM]. TEST ITEM", "Legendary Ring", "Right mouse button"]


def test_equipment_trace_requires_item_power_marker(monkeypatch):
    import src.tts

    grammar = LocaleGrammar.from_dict("enUS", {"labels": {"item_power": ["Item Power"]}, "rarities": {}})
    monkeypatch.setattr(src.tts, "Dataloader", lambda: SimpleNamespace(grammar=grammar))

    assert src.tts.is_equipment_trace(["Test Helm", "Legendary Helm", "900 Item Power"])
    assert not src.tts.is_equipment_trace(["Character", "New Legendary", "Equipment", "Mouse Left Button"])


def test_tts_cleaner_removes_locale_item_prefix():
    from src.tts import fix_data

    grammar = LocaleGrammar.from_dict("zhCN", {"labels": {"item_name_prefix": ["[收藏物品]."]}})

    assert fix_data("[收藏物品]. 无限法衣", grammar=grammar) == "无限法衣"


def test_tts_framer_rejects_shop_category_without_rarity_or_item_power():
    from src.tts import TtsFramer

    grammar = LocaleGrammar.from_dict(
        "zhCN", {"labels": {"item_end_control": ["鼠标右键"], "item_power": ["物品强度"]}, "rarities": {}}
    )
    catalog = SimpleNamespace(resolve_item_type=lambda value: "Ring" if value == "戒指" else None)
    framer = TtsFramer(grammar, catalog)

    for line in ["戒指", "戒指", "费用 : 50 古币"]:
        assert framer.feed(line) is None
    assert framer.feed("鼠标右键") is None

    framer = TtsFramer(grammar, catalog)
    for line in ["朴素戒指", "戒指", "850 物品强度"]:
        assert framer.feed(line) is None
    assert framer.feed("鼠标右键") == ["朴素戒指", "戒指", "850 物品强度", "鼠标右键"]


def test_parser_handles_full_width_comparison_and_variable_legendary_affixes(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    grammar = LocaleGrammar.from_dict(
        "zhCN", {"labels": {"armor": ["护甲值"], "affix_stop": ["需要等级"]}, "rarities": {}}
    )
    monkeypatch.setattr(parser, "Dataloader", lambda: SimpleNamespace(grammar=grammar))
    monkeypatch.setattr(
        parser,
        "_resolve_affix_name",
        lambda line, _item_type=None, **_kwargs: line if line.startswith("词缀") else None,
    )

    assert parser._get_index_of_armor_dps_or_all_resist(["装备名", "1,603 护甲值 （+0.9% 坚韧）"], "armor") == 1

    item = Item(rarity=ItemRarity.Legendary, item_type=ItemType.Gloves)
    section = ["词缀 1", "词缀 2", "词缀 3", "词缀 4", "词缀 5", "威能文本", "需要等级: 70"]
    assert parser._get_affix_counts(section, item, 0) == (0, 5)


def test_parser_stops_legendary_affixes_before_aspect_and_filled_gem(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    grammar = LocaleGrammar.from_dict("zhCN", {"labels": {"affix_stop": ["需要等级"]}, "rarities": {}})
    monkeypatch.setattr(parser, "Dataloader", lambda: SimpleNamespace(grammar=grammar))
    monkeypatch.setattr(
        parser,
        "_resolve_affix_name",
        lambda line, _item_type=None, **_kwargs: line if line.startswith("词缀") else None,
    )
    monkeypatch.setattr(parser, "_get_affix_starting_location_from_tts_section", lambda _section, _item: 0)
    item = Item(rarity=ItemRarity.Legendary, item_type=ItemType.Gloves, name="test_legendary")
    section = ["词缀 1", "词缀 2", "词缀 3", "词缀 4", "威能文本", "璀璨红宝石", "需要等级: 70"]

    _, affix_count, affixes, aspect_text = parser._compute_affix_layout(section, item)

    assert affix_count == 4
    assert affixes == section[:4]
    assert aspect_text == "威能文本"


def test_parser_strips_zhcn_duration_before_greater_affix_detection(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    monkeypatch.setattr(parser, "_resolve_affix_name", lambda _text, _item_type=None: "stun_duration")

    affix = parser._get_affix_from_text("5% 几率使敌人昏迷 [4 - 6]%，持续 2 秒")

    assert affix.type == AffixType.normal
    assert affix.value == 5
    assert affix.min_value == 4
    assert affix.max_value == 6


def test_unknown_mythic_fails_as_replayable_index_error_with_locations(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    monkeypatch.setattr(parser, "Dataloader", lambda: SimpleNamespace(aspect_unique_dict={}))
    item_parser = parser._TtsItemParser(["未知神话暗金"], attach_locations=True)
    item_parser.item = Item(rarity=ItemRarity.Mythic, name="unknown_mythic")

    with pytest.raises(IndexError, match="Unrecognized unique unknown_mythic"):
        item_parser._validate_unique()


def test_parser_counts_current_season_unique_affixes_until_unique_power(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    grammar = SimpleNamespace(startswith=lambda _label, _line: False)
    catalog = SimpleNamespace(grammar=grammar, aspect_unique_dict={"current_unique": {"num_inherents": 0}})
    monkeypatch.setattr(parser, "Dataloader", lambda: catalog)
    monkeypatch.setattr(
        parser,
        "_resolve_affix_name",
        lambda line, _item_type=None, **_kwargs: line if line.startswith("affix") else None,
    )
    monkeypatch.setattr(parser, "_get_affix_starting_location_from_tts_section", lambda _section, _item: 0)
    item = Item(rarity=ItemRarity.Unique, item_type=ItemType.Helm, name="current_unique")
    section = ["affix 1", "affix 2", "affix 3", "affix 4", "affix 5", "unique power"]

    _, affix_count, affixes, aspect_text = parser._compute_affix_layout(section, item)

    assert affix_count == 5
    assert affixes == section[:5]
    assert aspect_text == "unique power"


def test_alias_index_maps_canonical_keys_and_localized_displays():
    from src.dataloader import Dataloader

    aliases = Dataloader._alias_index({"of_celestial_strife": "天界纷争之威能"})
    catalog = object.__new__(Dataloader)
    catalog._aspect_aliases = aliases

    assert Dataloader._resolve_alias("of_celestial_strife", aliases) == "of_celestial_strife"
    assert Dataloader._resolve_alias("天界纷争之威能", aliases) == "of_celestial_strife"
    assert catalog.resolve_aspect("boneweave_gauntlets_of_celestial_strife") == "of_celestial_strife"
    assert catalog.resolve_aspect("带有天界纷争之威能的护手") == "of_celestial_strife"


def test_ambiguous_aliases_fail_closed():
    from src.dataloader import Dataloader

    aliases = Dataloader._alias_index({"first": "重名", "second": "重名"})
    catalog = object.__new__(Dataloader)
    catalog._aspect_aliases = Dataloader._alias_index({
        "short": "圣光",
        "long": "圣光之怒",
        "equal_left": "甲乙",
        "equal_right": "乙丙",
    })

    assert Dataloader._resolve_alias("重名", aliases) is None
    assert Dataloader._resolve_alias("first", aliases) == "first"
    assert Dataloader._resolve_alias("second", aliases) == "second"
    assert catalog.resolve_aspect("圣光之怒") == "long"
    assert catalog.resolve_aspect("甲乙丙") is None


def test_all_localized_aliases_are_indexed_without_provider_scope_filter():
    from src.dataloader import Dataloader

    aliases = Dataloader._alias_index({"current_poison": "毒素伤害", "provider_absent": "闪避给予移动速度"})

    assert Dataloader._resolve_alias("毒素伤害", aliases) == "current_poison"
    assert Dataloader._resolve_alias("闪避给予移动速度", aliases) == "provider_absent"


def test_item_type_aliases_prefer_locale_data_and_cover_parser_only_types():
    from src.dataloader import Dataloader

    aliases = Dataloader._item_type_alias_index({"ChestArmor": "胸甲"})

    assert Dataloader._resolve_alias("ChestArmor", aliases) == "ChestArmor"
    assert Dataloader._resolve_alias("胸甲", aliases) == "ChestArmor"
    assert Dataloader._resolve_alias("chest armor", aliases) is None
    assert Dataloader._resolve_alias("horadric seal", aliases) == "HoradricSeal"
    assert Dataloader._resolve_alias("未知类型", aliases) is None


def test_unique_alias_resolution_is_exact():
    from src.dataloader import Dataloader

    catalog = object.__new__(Dataloader)
    catalog._unique_aliases = Dataloader._unique_alias_index({
        "fists_of_fate": {"display_name": "命运之拳", "num_inherents": 0}
    })

    assert catalog.resolve_unique("fists_of_fate") == "fists_of_fate"
    assert catalog.resolve_unique("FISTS OF FATE") == "fists_of_fate"
    assert catalog.resolve_unique("命运之拳") == "fists_of_fate"
    assert catalog.resolve_unique("ARCHON GAUNTLETS OF INFESTATION") is None


def test_localized_sigil_resolution_is_category_safe_and_fails_on_ambiguity():
    from src.dataloader import Dataloader

    catalog = object.__new__(Dataloader)
    catalog.affix_sigil_dict_all = {
        "dungeons": {"test_dungeon": "测试地下城"},
        "major": {"barrier": "屏障 怪物获得屏障。"},
        "minor": {"barrier_minor": "屏障 怪物获得较弱的屏障。"},
        "positive": {},
    }
    catalog._sigil_aliases = {
        section: Dataloader._alias_index(entries) for section, entries in catalog.affix_sigil_dict_all.items()
    }

    assert catalog.resolve_sigil("测试地下城 位于哈维泽", "dungeons") == "test_dungeon"
    assert catalog.resolve_sigil("屏障 怪物获得屏障。", "major", "minor") == "barrier"
    assert catalog.resolve_sigil("屏障", "major", "minor") is None


def test_non_unique_item_name_does_not_use_unique_catalog(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    grammar = LocaleGrammar.from_dict(
        "enUS",
        {"labels": {"ancestral": ["ancestral"], "bloodied": ["bloodied"]}, "rarities": {"Legendary": ["legendary"]}},
    )
    unique_lookups: list[str] = []
    catalog = SimpleNamespace(
        bad_tts_uniques={},
        grammar=grammar,
        resolve_item_type=lambda value: "Gloves" if value == "gloves" else None,
        resolve_unique=lambda value: unique_lookups.append(value) or "fists_of_fate",
    )
    monkeypatch.setattr(parser, "Dataloader", lambda: catalog)

    item = parser._create_base_item_from_tts(["ARCHON GAUNTLETS OF INFESTATION", "Legendary Gloves", "800 Item Power"])

    assert item is not None
    assert item.name == "archon_gauntlets_of_infestation"
    assert unique_lookups == []


def test_unknown_localized_rarity_or_type_fails_closed(monkeypatch):
    import src.item.descr.read_descr_tts as parser

    grammar = LocaleGrammar.from_dict(
        "zhCN", {"labels": {"ancestral": ["先祖"], "bloodied": ["染血"]}, "rarities": {"Unique": ["暗金"]}}
    )
    catalog = SimpleNamespace(
        bad_tts_uniques={},
        grammar=grammar,
        resolve_item_type=lambda value: "Ring" if value == "戒指" else None,
        resolve_unique=lambda _value: "known_unique",
    )
    monkeypatch.setattr(parser, "Dataloader", lambda: catalog)

    assert parser._create_base_item_from_tts(["未知物品", "未知稀有度戒指", "925 物品强度"]) is None
    assert parser._create_base_item_from_tts(["未知物品", "暗金未知类型", "925 物品强度"]) is None


def test_loading_locale_data_does_not_mutate_item_type_enum():
    from src.dataloader import Dataloader

    Dataloader()
    assert ItemType.ChestArmor.value == "chest armor"
    assert ItemType.Incense.value == "incense"
    assert ItemType.Material.value == "material"
    assert ItemType.Sigil.value == "nightmare sigil"
