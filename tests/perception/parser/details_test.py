from types import SimpleNamespace

from src.item import AffixType, Dataloader, ItemRarity, ItemType
from src.item.data import loader as loader_module
from src.perception.parser import details
from src.perception.parser.details import (
    _get_affix_from_text,
    _get_index_of_armor_dps_or_all_resist,
    _get_item_rarity,
    _get_item_type,
)


def _use_zhcn_catalog(monkeypatch) -> Dataloader:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(loader_module, "get_settings", lambda: settings)
    catalog = object.__new__(Dataloader)
    catalog.load_data()
    monkeypatch.setattr(details, "Dataloader", lambda: catalog)
    return catalog


def test_parser_details_maps_rarity_and_item_type_labels() -> None:
    assert _get_item_rarity("legendary") is ItemRarity.Legendary
    assert _get_item_type("sword") is ItemType.Sword


def test_parser_details_maps_zhcn_rarity_type_and_anchor(monkeypatch) -> None:
    _use_zhcn_catalog(monkeypatch)

    assert _get_item_rarity("先祖神话暗金双手剑") is ItemRarity.Mythic
    assert _get_item_type("双手剑") is ItemType.Sword2H
    assert _get_index_of_armor_dps_or_all_resist(["装备名", "1,603 护甲值 （+0.9% 坚韧）"], "armor") == 1


def test_parser_details_disambiguates_zhcn_affixes_by_range_precision(monkeypatch) -> None:
    _use_zhcn_catalog(monkeypatch)

    integer_affix = _get_affix_from_text("+5% 暗影伤害 [4 - 6]%")
    decimal_affix = _get_affix_from_text("+5.0% 暗影伤害 [4.0 - 6.0]%")

    assert integer_affix.name == "shadow_damage"
    assert decimal_affix.name == "shade_damage"


def test_parser_details_removes_zhcn_duration_before_greater_affix_detection(monkeypatch) -> None:
    _use_zhcn_catalog(monkeypatch)
    monkeypatch.setattr(details, "_resolve_affix_name", lambda _text, _item_type=None: "stun_duration")

    affix = _get_affix_from_text("5% 击昏的持续时间 [4 - 6]%，持续 2 秒")

    assert affix.type is AffixType.normal
    assert affix.value == 5
    assert affix.min_value == 4
    assert affix.max_value == 6
