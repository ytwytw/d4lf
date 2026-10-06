from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog, ItemRarity, ItemType
from src.game_data import catalog as catalog_module
from src.perception.parser import details
from src.perception.parser.details import _get_item_rarity, _get_item_type


def _use_catalog(monkeypatch, language: str) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language=language))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(details, "GameCatalog", lambda: catalog)
    return catalog


def _use_zhcn_catalog(monkeypatch) -> GameCatalog:
    return _use_catalog(monkeypatch, "zhCN")


def test_parser_details_maps_rarity_and_item_type_labels(monkeypatch) -> None:
    _use_catalog(monkeypatch, "enUS")

    assert _get_item_rarity("legendary") is ItemRarity.Legendary
    assert _get_item_type("sword") is ItemType.Sword


def test_parser_details_accepts_item_type_enum_names_and_catalog_labels(monkeypatch) -> None:
    catalog = GameCatalog()
    monkeypatch.setattr(catalog, "item_types_dict", {**catalog.item_types_dict, "Incense": "Encens"})

    assert _get_item_type("Incense") is ItemType.Incense
    assert _get_item_type("incense") is ItemType.Incense
    assert _get_item_type("Encens") is ItemType.Incense


@pytest.mark.parametrize(
    ("language", "name"), [("zhCN", "彼消我长之冒险者的短衣"), ("enUS", "adventurers_tunic_of_dominance")]
)
def test_legendary_aspect_uses_localized_aliases(monkeypatch, language, name) -> None:
    _use_catalog(monkeypatch, language)

    aspect = details._get_aspect_from_name("Controls grant resolve", name)

    assert aspect is not None
    assert aspect.name == "of_dominance"


@pytest.mark.parametrize(
    ("language", "text", "canonical", "value"),
    [
        ("zhCN", "x30% 暴击伤害增倍 [26 - 50]%", "critical_strike_damage_multiplier", 30),
        ("zhCN", "x14% 暗影 伤害增倍 [14 - 20]%", "shadow_damage_multiplier", 14),
        ("enUS", "x24% Shadow Damage Multiplier [14 - 24]%", "shadow_damage_multiplier", 24),
    ],
)
def test_multiplier_affixes_preserve_localized_x_prefix(monkeypatch, language, text, canonical, value) -> None:
    _use_catalog(monkeypatch, language)

    affix = details._get_affix_from_text(text, ItemType.Mace2H)

    assert affix.name == canonical
    assert affix.value == value
    assert details._is_known_affix_text(text, ItemType.Mace2H)


@pytest.mark.parametrize(("language", "text"), [("zhCN", "赛斯切隆怒火"), ("enUS", "Sescherons Fury")])
def test_set_labels_resolve_to_profile_ids(monkeypatch, language, text) -> None:
    _use_catalog(monkeypatch, language)

    assert details._get_set_from_text(text) == "sescherons_fury"


@pytest.mark.parametrize(
    ("language", "text", "codex", "cosmetic"),
    [
        ("zhCN", "分解以升级能量法典中的威能", True, False),
        ("zhCN", "分解以解锁能量法典中的新威能", True, False),
        ("zhCN", "分解以解锁新外观", False, True),
        ("enUS", "Upgrades an Aspect in the Codex of Power", True, False),
        ("enUS", "Unlocks new Aspect", True, False),
        ("enUS", "Unlocks new look on salvage", False, True),
        ("zhCN", "需要等级 70", False, False),
    ],
)
def test_upgrade_flags_use_locale_grammar(monkeypatch, language, text, codex, cosmetic) -> None:
    _use_catalog(monkeypatch, language)

    assert details._is_codex_upgrade([text]) is codex
    assert details._is_cosmetic_upgrade([text]) is cosmetic


@pytest.mark.parametrize("name", ["恶毒之胸甲", "未知新威能之胸甲"])
def test_legendary_aspect_rejects_unknown_or_ambiguous_translation(monkeypatch, name) -> None:
    _use_zhcn_catalog(monkeypatch)

    with pytest.raises(ValueError, match="legendary aspect"):
        details._get_aspect_from_name("未识别威能说明", name)


@pytest.mark.parametrize("text", ["+10.5% 攻击速度 [8 - 12]%", "+10.5% 攻击速度 [8.0 - 12]%"])
def test_affix_numeric_roll_does_not_truncate_mixed_precision(monkeypatch, text) -> None:
    _use_zhcn_catalog(monkeypatch)

    affix = details._get_affix_from_text(text)

    assert affix.name == "attack_speed"
    assert (affix.value, affix.min_value, affix.max_value) == (10.5, 8, 12)


@pytest.mark.parametrize("text", ["解锁 5 个神符插槽", "解锁 4 个神符槽位"])
def test_seal_slot_label_is_normal_not_a_greater_affix(monkeypatch, text) -> None:
    _use_zhcn_catalog(monkeypatch)

    affix = details._get_affix_from_text(text, ItemType.HoradricSeal)

    assert affix.name == "charm_slot"
    assert affix.value == (4 if "槽位" in text else 5)
    assert affix.type.name == "normal"


def test_english_fallback_affix_cannot_resolve_chinese_text(monkeypatch) -> None:
    catalog = _use_zhcn_catalog(monkeypatch)
    assert catalog.affix_dict["resistance"] == "resistance"  # the unresolved record keeps its English text
    with pytest.raises(ValueError, match="Could not resolve affix name"):
        details._get_affix_from_text("+12% 未知抗性 [10 - 15]%", ItemType.Ring)
