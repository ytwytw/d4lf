"""Legacy pools asking for more matches than they list load with a warning and mean "all listed"."""

import logging
from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from src.game_data import ItemRarity, ItemType
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.pools import oversized_pools
from src.item.filter.repository import ProfileRulesRepository
from src.item.filter.rules import EvaluationSettings, LoadedRules
from src.profiles import AffixFilterCountModel, AffixFilterModel, ItemFilterModel, ProfileModel
from src.settings import AspectFilterType

if TYPE_CHECKING:
    from src.settings import Settings

LEGACY = (
    "Affixes:\n- Helm:\n    itemType: [helm]\n    affixPool:\n    - count:\n"
    "      - {name: willpower}\n      - {name: maximum_life}\n      minCount: 3\n"
)


def test_oversized_pools_names_each_affected_pool() -> None:
    pool = AffixFilterCountModel(count=[AffixFilterModel(name="willpower")], minCount=2)
    profile = ProfileModel(name="p", Affixes=[{"Helm": ItemFilterModel(affix_pool=[pool], inherent_pool=[pool])}])
    assert oversized_pools(profile) == [
        "Affixes.Helm.affix_pool[1] minCount 2 exceeds its 1 listed affixes",
        "Affixes.Helm.inherent_pool[1] minCount 2 exceeds its 1 listed affixes",
    ]
    assert oversized_pools(ProfileModel(name="ok", Affixes=[{"Helm": ItemFilterModel(affix_pool=[])}])) == []


def test_legacy_oversized_pool_loads_with_warning_and_requires_all_listed(tmp_path, caplog) -> None:
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "legacy.yaml").write_text(LEGACY, encoding="utf-8")
    settings = SimpleNamespace(user_dir=tmp_path, general=SimpleNamespace(profiles=["legacy"]))
    with caplog.at_level(logging.WARNING):
        rules = ProfileRulesRepository(lambda: cast("Settings", settings)).load_files()
    assert "minCount 3 exceeds its 2 listed affixes" in caplog.text
    evaluator = FilterEvaluator(
        rules=replace(LoadedRules.empty(), affix_filters=rules.affix_filters),
        evaluation_settings=EvaluationSettings(keep_aspects=AspectFilterType.none),
    )

    def keeps(*names: str) -> bool:
        affixes = [Affix(name=name) for name in names]
        return evaluator.should_keep(
            Item(item_type=ItemType.Helm, rarity=ItemRarity.Rare, power=800, affixes=affixes)
        ).keep

    assert keeps("willpower", "maximum_life")
    assert not keeps("willpower")
