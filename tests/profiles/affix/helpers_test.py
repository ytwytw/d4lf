import importlib

from src.game_data import GameCatalog, ItemType
from src.profiles.affix.helpers import _item_type_summary


def test_helpers_module_is_importable() -> None:
    module = importlib.import_module("src.profiles.affix.helpers")
    assert hasattr(module, "get_affixes_for_set")


def test_item_type_summary_uses_catalog_labels(monkeypatch) -> None:
    catalog = GameCatalog()
    # Keep the fallback case independent of the language loaded by earlier tests.
    monkeypatch.setattr(catalog, "item_types_dict", {"Helm": "Casque"})

    assert _item_type_summary([ItemType.Helm, ItemType.Sword]) == "Casque, sword"
