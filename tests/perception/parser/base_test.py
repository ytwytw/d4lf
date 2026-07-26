from types import SimpleNamespace

import pytest

from src.item import Dataloader, ItemRarity, ItemType
from src.item.data import loader as loader_module
from src.perception.parser import base, details
from src.perception.parser.base import _create_base_item_from_tts, _is_charm_slot_unlock


def _use_zhcn_catalog(monkeypatch) -> Dataloader:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(loader_module, "get_settings", lambda: settings)
    catalog = object.__new__(Dataloader)
    catalog.load_data()
    monkeypatch.setattr(base, "Dataloader", lambda: catalog)
    monkeypatch.setattr(details, "Dataloader", lambda: catalog)
    return catalog


def test_parser_base_identifies_charm_slot_unlocks() -> None:
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
