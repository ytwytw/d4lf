"""Editor labels change only where localized text is shared by several canonical identities."""

from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog
from src.game_data import catalog as catalog_module
from src.profiles.labels import affix_labels, disambiguate, tribute_labels


@pytest.fixture
def zh(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", catalog)
    return catalog


def test_disambiguate_changes_only_colliding_labels() -> None:
    labels = disambiguate({"a": "同名", "b": "同名", "c": "唯一"}, {"a": "detail a"}, "zhCN")
    assert labels == {"a": "同名（detail a）", "b": "同名（b）", "c": "唯一"}
    assert disambiguate({"a": "X", "b": "X"}, {"a": "d", "b": "d"}) == {"a": "X (d) [a]", "b": "X (d) [b]"}


@pytest.mark.parametrize("language", ["zhCN", "enUS"])
def test_every_editor_label_is_unique_for_shipped_data(monkeypatch, language) -> None:
    settings = SimpleNamespace(general=SimpleNamespace(language=language))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    for source in (catalog.affix_dict, catalog.charm_affix_dict, catalog.seal_affix_dict):
        labels = affix_labels(source, catalog)
        assert labels.keys() == source.keys()
        assert len(set(labels.values())) == len(labels)
        assert all(labels[key] == value for key, value in source.items() if list(source.values()).count(value) == 1)
    tributes = tribute_labels(catalog)
    assert len(set(tributes.values())) == len(tributes) == len(catalog.tribute_dict)


def test_shared_zh_labels_get_truthful_details(zh) -> None:
    tributes = tribute_labels()
    assert tributes["tribute_of_heritage"] == "巨人贡品（tribute of heritage · 职业专属暗金物品）"
    assert tributes["tribute_of_titans"] == "巨人贡品（tribute of titans · 巢穴首领秘宝钥匙）"
    affixes = affix_labels(zh.affix_dict)
    assert affixes["poison_damage"] == "毒素伤害（poison damage · 整数范围）"
    assert affixes["poisoning_damage"] == "毒素伤害（poisoning damage · 小数范围）"
    assert affixes["maximum_life"] == zh.affix_dict["maximum_life"]
