from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from lxml import html

from src.game_data import GameCatalog, ItemRarity, ItemType
from src.game_data import catalog as catalog_module
from src.importing import ImportRequest
from src.importing.d4builds import variants
from src.importing.d4builds.metadata import D4BuildsError
from src.importing.d4builds.variants import extract_variant
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.rules import EvaluationSettings, LoadedRules
from src.perception import clean_str, closest_match
from src.profiles import DynamicItemFilterModel
from src.settings import AspectFilterType

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


def test_extract_variant_reports_missing_items() -> None:
    with pytest.raises(D4BuildsError, match="No items found"):
        extract_variant(
            data=html.fromstring("<html><body></body></html>"),
            driver=cast("WebDriver", object()),
            request=ImportRequest("https://d4builds.gg/builds/example-build"),
            class_name="barbarian",
            build_header="Bash",
            variant_name="Pit Push",
        )


def _group(slot: str, names: list[str]) -> str:
    stats = "".join(
        f'<div class="filled"><div><div class="dropdown__button__wrapper"><span>{name}</span></div></div></div>'
        for name in names
    )
    return f'<div class="builder__stats__group"><i class="builder__stats__slot"></i><i class="builder__stats__slot"></i>{slot}{stats}</div>'


def test_unreadable_stats_broaden_slots_and_unknown_uniques_are_unsafe(mock_ini_loader, monkeypatch) -> None:
    monkeypatch.setattr(variants, "_get_weapon_paperdoll_icons", lambda **_kwargs: {})
    monkeypatch.setattr(variants, "_extract_d4builds_seal_charm_filters", lambda **_kwargs: ([], []))
    monkeypatch.setattr(variants, "extract_d4builds_paragon_steps", lambda *_args, **_kwargs: None)
    gear = "".join(
        f'<div class="builder__gear__item"><div class="builder__gear__slot">{slot}</div>{extra}</div>'
        for slot, extra in (("Helm", ""), ("Ring", ""), ("Amulet", '<b class="builder__gear__name--unique">Future</b>'))
    )
    stats = _group("Helm", ["Maximum Life", "", "", ""]) + _group("Ring", []) + _group("Amulet", ["Maximum Life"])
    page = f'<html><body><div class="builder__gear__items">{gear}</div><div class="builder__stats__list">{stats}</div></body></html>'
    variant = extract_variant(
        data=html.fromstring(page),
        driver=cast("WebDriver", object()),
        request=ImportRequest("https://d4builds.gg/builds/example-build"),
        class_name="barbarian",
        build_header="Bash",
        variant_name="Pit Push",
    )
    assert [(rule.item_type, rule.affix_pool) for rule in variant.affix_filters] == [
        ([ItemType.Helm], []),  # three of four listed stats were unreadable
        ([ItemType.Ring], []),  # filled slot without readable stats
    ]
    assert variant.unsafe_slots == ["slot Amulet unique Future"]


def test_english_stats_keep_their_identity_under_a_chinese_runtime(mock_ini_loader, monkeypatch) -> None:
    chinese = object.__new__(GameCatalog)
    zh_settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: zh_settings)
    chinese.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", chinese)
    # Before: the stat was looked up among the Chinese labels, so any similarity "match" was a different affix.
    assert closest_match(clean_str("Maximum Life"), chinese.affix_dict) != "maximum_life"
    monkeypatch.setattr(variants, "_get_weapon_paperdoll_icons", lambda **_kwargs: {})
    monkeypatch.setattr(variants, "_extract_d4builds_seal_charm_filters", lambda **_kwargs: ([], []))
    monkeypatch.setattr(variants, "extract_d4builds_paragon_steps", lambda *_args, **_kwargs: None)
    stats = _group("Helm", ["Maximum Life", "Total Armor", "Cooldown Reduction", "Dodge Chance"])
    gear = '<div class="builder__gear__item"><div class="builder__gear__slot">Helm</div></div>'
    page = f'<html><body><div class="builder__gear__items">{gear}</div><div class="builder__stats__list">{stats}</div></body></html>'
    variant = extract_variant(
        data=html.fromstring(page),
        driver=cast("WebDriver", object()),
        request=ImportRequest("https://d4builds.gg/builds/example-build"),
        class_name="barbarian",
        build_header="Bash",
        variant_name="Pit Push",
    )
    (rule,) = variant.affix_filters
    wanted = ["maximum_life", "total_armor", "cooldown_reduction", "dodge_chance"]
    assert [affix.name for affix in rule.affix_pool[0].count] == wanted
    rules = replace(LoadedRules.empty(), affix_filters={"p": [DynamicItemFilterModel(root={"helm": rule})]})
    helm = Item(
        item_type=ItemType.Helm, rarity=ItemRarity.Legendary, power=800, affixes=[Affix(name=n) for n in wanted[:3]]
    )
    evaluator = FilterEvaluator(rules, EvaluationSettings(keep_aspects=AspectFilterType.none))
    assert evaluator.should_keep(helm).keep
