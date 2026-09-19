import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import perception
from src.game_data import GameCatalog, ItemRarity, ItemType
from src.game_data import catalog as catalog_module
from src.item import AffixType, Aspect, Item
from src.perception import parse_item_text

pytestmark = pytest.mark.usefixtures("english_catalog")


@pytest.fixture
def english_catalog(monkeypatch) -> None:
    _use_catalog(monkeypatch, "enUS")


def _use_catalog(monkeypatch, language: str) -> None:
    settings = SimpleNamespace(general=SimpleNamespace(language=language))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", catalog)


@pytest.mark.parametrize(
    "case",
    [
        case
        for name in ("zhcn_live_smoke.json", "zhcn_live_talisman.json", "zhcn_live_tributes.json")
        for case in json.loads((Path(__file__).parents[1] / "data" / name).read_text(encoding="utf-8"))
    ],
    ids=lambda case: case["input"][0],
)
def test_real_zhcn_equipment_and_backpack_capture(monkeypatch, case) -> None:
    _use_catalog(monkeypatch, "zhCN")

    item = parse_item_text(case["input"])
    expected = case["expected"]

    assert item is not None
    assert item.item_type is ItemType[expected["type"]]
    assert item.rarity is ItemRarity[expected["rarity"]]
    assert item.power == expected["power"]
    if "name" in expected:
        assert item.name == expected["name"]
    assert [[affix.name, affix.value] for affix in item.affixes] == expected["affixes"]
    assert (item.aspect.name if item.aspect else None) == expected["aspect"]
    assert (item.aspect.value if item.aspect else None) == expected["aspect_value"]
    if "set" in expected:
        assert item.set == expected["set"]
    if "inherent" in expected:
        assert [[affix.name, affix.value] for affix in item.inherent] == expected["inherent"]
    if "affix_types" in expected:
        assert [affix.type.name for affix in item.affixes] == expected["affix_types"]
    if item.rarity is ItemRarity.Unique:
        assert item.name == expected["aspect"]


@pytest.mark.parametrize("missing", ["power", "affixes", "aspect"])
def test_incomplete_equipment_capture_fails_closed(monkeypatch, missing) -> None:
    _use_catalog(monkeypatch, "zhCN")
    trace = json.loads((Path(__file__).parents[1] / "data/zhcn_live_smoke.json").read_text(encoding="utf-8"))[0][
        "input"
    ]
    if missing == "power":
        trace.pop(2)
    else:
        trace = trace[: (6 if missing == "affixes" else 8)] + ["鼠标右键"]

    with pytest.raises(ValueError, match="Missing|Incomplete"):
        parse_item_text(trace)


def test_captured_tts_cases_parse_without_item_description_modules(parser_cases) -> None:
    for input_item, expected_item in parser_cases:
        assert parse_item_text(input_item) == expected_item


LOOT_FILTER_TTS = ["SELECT ALL", "Checkbox Disabled", "Item Power Range", "Left mouse button"]


def test_loot_filter_controls_are_not_tts_item_start() -> None:
    assert perception.find_item_start(LOOT_FILTER_TTS) is None


def test_loot_filter_controls_do_not_raise_tts_parser_error() -> None:
    assert parse_item_text(LOOT_FILTER_TTS) is None


def test_captured_filters_screen_is_not_an_item() -> None:
    assert (
        parse_item_text([
            "FILTERS",
            *("Checkbox Disabled",) * 12,
            "Search",
            "&lt;CC&gt; Panoramix | 70 (300)",
            "Chest 7",
            "Chest 6",
            "Chest 5",
            "Chest 4",
            "Chest 3",
            "Consumables",
            "Chest 1",
            "Consumables",
            "Chest 3",
            "Chest 3",
            "Stash",
            "Left mouse button",
        ])
        is None
    )


def test_parser_returns_non_equipment_items_without_image_lookup() -> None:
    item_text = ["GREATER MATERIALS CACHE", "Legendary Cache"]

    assert parse_item_text(item_text) == Item(item_type=ItemType.Cache, original_name="GREATER MATERIALS CACHE")


def test_parser_returns_boss_keys_without_image_lookup() -> None:
    item_text = ["MALIGNANT HEART", "Legendary Boss Key"]

    assert parse_item_text(item_text) == Item(item_type=ItemType.LairBossKey, original_name="MALIGNANT HEART")


def test_legendary_horadric_seal_parses_item_power_charm_slots_as_inherent() -> None:
    item_text = [
        "SHIELDING HORADRIC SEAL OF ILL-TEMPERANCE",
        "Legendary Horadric Seal",
        "850 Item Power",
        "Unlocks 5 Charm Slots",
        "+11.6% Barrier Generation [8.0 - 12.0]% (+11.6%)",
        "Sescherons Fury:. +9% [8 - 11]% Fury Generation",
        "Berserkers Crucible:. Lucky Hit: Up to a 7% [7 - 9]% chance to Become Berserking",
        "Properties lost when equipped:",
        "Unlocks 1 Charm Slots",
        "18.0%[x] Critical Strike Damage",
        "Seal Power",
        "Seal Power",
        "Requires Level 50. Lord of Hatred Item",
        "Sell Value: 13,386,186 Gold",
        "Right mouse button",
    ]

    item = parse_item_text(item_text)

    assert item is not None
    assert [(affix.name, affix.text, affix.value, affix.type) for affix in item.inherent] == [
        ("charm_slot", "Unlocks 5 Charm Slots", 5.0, AffixType.inherent)
    ]
    assert [affix.name for affix in item.affixes] == [
        "barrier_generation",
        "sescherons_fury_fury_generation",
        "berserkers_crucible_lucky_hit_up_to_a_chance_to_become_berserking",
    ]


def test_unique_helm_with_armory_loadout_has_five_affixes_and_one_aspect() -> None:
    item_text = [
        "GODSLAYER CROWN",
        "Ancestral Unique Helm",
        "900 Item Power",
        "25 ( +25) Quality",
        "Armory Loadout",
        "2,004 Armor",
        "+128 Dexterity +[100 - 121]",
        "+1,754 Maximum Life [1,226 - 1,450]",
        "+35 Maximum Resource [15 - 20]",
        "+1,348 Armor [981 - 1,225]",
        "+3,000 Armor",
        "When you attempt to Incapacitate an enemy, you mark them and all surrounding enemies, pulling them in and dealing 7.5%[x] [7.5 - 10.0]% increased damage to them.",
        "CirMot (300/150) - Lethargic Shadow",
        "Cast 5 Skills then become exhausted for 3 seconds. (1 time). Gain 2 shadows, from the Rogues Dark Shroud Skill, reducing damage taken per shadow. . (Overflow: Gain Multiple Shadows)",
        "The Sahptev faithful believe in a thousand and one gods. If it takes me as many lifetimes, I will find and kill them all.. - Gaspar Stilbian, Veradani Outcast",
        "Requires Level 70. Account Bound. Unique Equipped. Vessel of Hatred Item",
        "Crafted",
        "Sell Value: 114,593 Gold",
        "Durability: 100/100. Tempers: 1/4",
        "Right mouse button",
    ]

    item = parse_item_text(item_text)

    assert item is not None
    assert [affix.text for affix in item.affixes] == [
        "+128 Dexterity +[100 - 121]",
        "+1,754 Maximum Life [1,226 - 1,450]",
        "+35 Maximum Resource [15 - 20]",
        "+1,348 Armor [981 - 1,225]",
        "+3,000 Armor",
    ]
    assert [(affix.name, affix.value, affix.min_value, affix.max_value, affix.type) for affix in item.affixes] == [
        ("dexterity", 128.0, 100.0, 121.0, AffixType.normal),
        ("maximum_life", 1754.0, 1226.0, 1450.0, AffixType.normal),
        ("maximum_resource", 35.0, 15.0, 20.0, AffixType.normal),
        ("armor", 1348.0, 981.0, 1225.0, AffixType.normal),
        ("armor", 3000.0, None, None, AffixType.greater),
    ]
    assert item.aspect == Aspect(
        name="godslayer_crown",
        min_value=7.5,
        max_value=10.0,
        text="When you attempt to Incapacitate an enemy, you mark them and all surrounding enemies, pulling them in and dealing 7.5%[x] [7.5 - 10.0]% increased damage to them.",
        value=7.5,
    )


def test_sigil_rarity_is_derived_from_tts_affixes() -> None:
    item_text = [
        "Nightmare Sigil",
        "Transform this dungeon into. aNightmare Dungeon",
        "Beast Graveyard in Nahantu",
        "DUNGEON AFFIXES",
        "Horadric Strongroom",
        "This place will always contain a Horadric Strongroom.",
        "Hellbound Elites",
        "Elite monsters have the Hellbound affix and deal 20% more damage.",
        "Account Bound. Vessel of Hatred Item",
        "Sell Value: 1 Gold",
        "Right mouse button",
    ]

    item = parse_item_text(item_text)

    assert item is not None
    assert item.item_type == ItemType.Sigil
    assert item.name == "beast_graveyard"
    assert [affix.name for affix in item.affixes] == ["horadric_strongroom", "hellbound_elites"]
    assert item.rarity == ItemRarity.Rare


def test_localized_set_charm_uses_verified_type_and_set_aliases(monkeypatch) -> None:
    _use_catalog(monkeypatch, "zhCN")
    item = parse_item_text([
        "测试神符",
        "套装神符",
        "850 物品强度",
        "+10% 攻击速度 [8 - 12]%",
        "+810 荆棘 [576 - 865]",
        "赛斯切隆怒火",
        "需要等级 70",
        "鼠标右键",
    ])

    assert item is not None
    assert item.item_type is ItemType.Charm
    assert item.set == "sescherons_fury"
    assert [affix.name for affix in item.affixes] == ["attack_speed", "thorns"]


def test_unknown_set_charm_is_rejected_instead_of_junked_as_incomplete_item(monkeypatch) -> None:
    _use_catalog(monkeypatch, "zhCN")

    with pytest.raises(ValueError, match="set name"):
        parse_item_text([
            "测试神符",
            "套装神符",
            "850 物品强度",
            "+10% 攻击速度 [8 - 12]%",
            "+810 荆棘 [576 - 865]",
            "未有来源的套装",
            "鼠标右键",
        ])


def test_chinese_legendary_seal_parses_charm_slot_without_legendary_aspect(monkeypatch) -> None:
    _use_catalog(monkeypatch, "zhCN")
    item = parse_item_text([
        "测试封印",
        "传奇赫拉迪姆封印",
        "850 物品强度",
        "解锁 5 个神符插槽",
        "+10% 攻击速度 [8 - 12]%",
        "+810 荆棘 [576 - 865]",
        "+746 生命上限 [741 - 1000]",
        "需要等级 70",
        "鼠标右键",
    ])

    assert item is not None
    assert item.item_type is ItemType.HoradricSeal
    assert [(affix.name, affix.value) for affix in item.inherent] == [("charm_slot", 5)]
    assert len(item.affixes) == 3
    assert item.aspect is None
