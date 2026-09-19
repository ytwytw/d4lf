from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog, ItemRarity, ItemType
from src.game_data import catalog as catalog_module
from src.item import Item
from src.perception import text as text_module
from src.perception.parser import base, details
from src.perception.parser.base import _create_base_item_from_tts, _is_charm_slot_unlock


def _use_catalog(monkeypatch, language: str) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language=language))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(base, "GameCatalog", lambda: catalog)
    monkeypatch.setattr(details, "GameCatalog", lambda: catalog)
    monkeypatch.setattr(text_module, "GameCatalog", lambda: catalog)
    return catalog


def _use_zhcn_catalog(monkeypatch) -> GameCatalog:
    return _use_catalog(monkeypatch, "zhCN")


def test_parser_base_identifies_charm_slot_unlocks(monkeypatch) -> None:
    _use_catalog(monkeypatch, "enUS")

    assert _is_charm_slot_unlock("Unlocks 5 Charm Slots")
    assert not _is_charm_slot_unlock("+10% Movement Speed")


@pytest.mark.parametrize(
    ("name", "metadata", "rarity", "item_type", "canonical_name"),
    [
        ("朴素长剑", "普通剑", ItemRarity.Common, ItemType.Sword, "朴素长剑"),
        ("魔法护手", "魔法手套", ItemRarity.Magic, ItemType.Gloves, "魔法护手"),
        ("稀有指环", "稀有戒指", ItemRarity.Rare, ItemType.Ring, "稀有指环"),
        ("传奇胸甲", "先祖传奇胸甲", ItemRarity.Legendary, ItemType.ChestArmor, "传奇胸甲"),
        ("谐角之冠", "先祖暗金头盔", ItemRarity.Unique, ItemType.Helm, "harlequin_crest"),
        ("祖父", "先祖神话暗金双手剑", ItemRarity.Mythic, ItemType.Sword2H, "the_grandfather"),
    ],
)
def test_create_base_item_maps_zhcn_headers_to_stable_ids(
    monkeypatch, name, metadata, rarity, item_type, canonical_name
) -> None:
    _use_zhcn_catalog(monkeypatch)

    item = _create_base_item_from_tts([name, metadata, "925 物品强度"])

    assert item is not None
    assert item.rarity is rarity
    assert item.item_type is item_type
    assert item.name == canonical_name
    assert item.power == 925


def test_create_base_item_rejects_unknown_zhcn_rarity_or_type(monkeypatch) -> None:
    _use_zhcn_catalog(monkeypatch)

    assert _create_base_item_from_tts(["未知物品", "未知稀有度戒指", "925 物品强度"]) is None
    assert _create_base_item_from_tts(["未知物品", "暗金未知类型", "925 物品强度"]) is None


@pytest.mark.parametrize("metadata", ["稀有巨人贡品", "稀有 巨人贡品"])
def test_chinese_tribute_header_does_not_require_spaces(monkeypatch, metadata) -> None:
    _use_zhcn_catalog(monkeypatch)

    item = _create_base_item_from_tts(["巨人贡品 (4)", metadata])

    assert item is not None
    assert item.item_type is ItemType.Tribute
    assert item.name == "tribute_of_titans"
    assert item.rarity is ItemRarity.Rare


def test_unique_charm_does_not_inherit_equipment_inherent_count(monkeypatch) -> None:
    _use_catalog(monkeypatch, "enUS")
    charm = Item(name="the_grandfather", item_type=ItemType.Charm, rarity=ItemRarity.Mythic)

    inherent_count, _ = base._get_affix_counts([], charm, 0)

    assert inherent_count == 0


def test_unknown_chinese_tribute_name_is_not_returned_as_a_profile_key(monkeypatch) -> None:
    _use_zhcn_catalog(monkeypatch)

    with pytest.raises(ValueError, match="tribute name"):
        _create_base_item_from_tts(["未确认译名贡品", "稀有未确认译名贡品"])


@pytest.mark.parametrize(
    ("name", "affix", "message"),
    [("未知地下城", "赫拉迪姆密室", "sigil dungeon"), ("beast graveyard", "未知词缀", "sigil affix")],
)
def test_unknown_sigil_reference_fails_closed(monkeypatch, name, affix, message) -> None:
    _use_zhcn_catalog(monkeypatch)
    trace = ["梦魇符印", "说明", name, "词缀", affix, "说明", "未知次要词缀", "说明", "鼠标右键"]

    with pytest.raises(ValueError, match=message):
        base._add_sigil_affixes_from_tts(trace, Item(item_type=ItemType.Sigil))
