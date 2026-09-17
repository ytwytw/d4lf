from types import SimpleNamespace

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
