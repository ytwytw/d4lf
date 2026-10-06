from dataclasses import replace

import pytest

from src.game_data import GameCatalog, ItemRarity, ItemType
from src.importing.d2core.catalog import CatalogStore, CatalogTransport
from src.importing.d2core.optional import normalize_talismans
from src.item import Affix, Item
from src.item.filter.evaluator import FilterEvaluator
from src.item.filter.rules import LoadedRules
from src.profiles import DynamicCharmFilterModel


def test_disabled_talisman_category_is_silent() -> None:
    affix_key = next(iter(GameCatalog().charm_affix_dict))
    catalogs = CatalogStore(
        version="v1",
        transport=CatalogTransport(),
        data={
            "talisman": {
                "charm": {"charm-key": {"key": "charm-key", "name": "Charm"}},
                "seal": {"seal-key": {"key": "seal-key", "name": "Seal"}},
                "itemSets": {},
                "affixes": {
                    "charm": {affix_key: {"key": affix_key, "desc": GameCatalog().charm_affix_dict[affix_key]}},
                    "seal": {},
                },
            }
        },
    )
    warnings: list[tuple[str, str, str, str]] = []

    def warn(code: str, variant: str, module: str, key: str) -> None:
        warnings.append((code, variant, module, key))

    charms, seals = normalize_talismans(
        {
            "charms": [
                {"type": "Charm", "key": "charm-key", "mods": [{"name": affix_key}]},
                {"type": "HoradricSeal", "key": "seal-key", "mods": []},
            ]
        },
        variant_name="Variant 1",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_charms=True,
        import_seals=False,
        warn=warn,
    )

    assert len(charms) == 1
    assert not seals
    assert not warnings


def test_charm_set_and_unique_claim_is_rejected_even_when_set_join_is_missing() -> None:
    catalogs = CatalogStore(
        version="v1",
        transport=CatalogTransport(),
        data={
            "talisman": {
                "charm": {"charm-key": {"key": "charm-key", "name": "Charm", "set": "missing-set"}},
                "seal": {},
                "itemSets": {},
                "affixes": {"charm": {}, "seal": {}},
            }
        },
    )
    warnings: list[tuple[str, str, str, str]] = []

    unsafe: list[str] = []
    charms, seals = normalize_talismans(
        {"charms": [{"type": "Charm", "key": "charm-key", "itemQuality": "Unique"}]},
        variant_name="Variant 1",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_charms=True,
        import_seals=True,
        warn=lambda *warning: warnings.append(warning),
        unsafe_charms=unsafe,
    )

    assert not charms
    assert not seals
    assert warnings == [("D2C-W120", "Variant 1", "charm", "charm-key")]
    assert unsafe == ["charm charm-key (set and unique)"]  # rejects the import instead of dropping the charm


def _talismans(entries, affix_keys):
    charm_dict = GameCatalog().charm_affix_dict
    catalogs = CatalogStore(
        version="v1",
        transport=CatalogTransport(),
        data={
            "talisman": {
                "charm": {"charm-key": {"key": "charm-key", "name": "Charm"}},
                "seal": {},
                "itemSets": {},
                "affixes": {"charm": {key: {"key": key, "desc": charm_dict[key]} for key in affix_keys}, "seal": {}},
            }
        },
    )
    unsafe_charms: list[str] = []
    unsafe_seals: list[str] = []
    charms, seals = normalize_talismans(
        {"charms": entries},
        variant_name="Variant 1",
        catalogs=catalogs,
        import_greater_affixes=False,
        require_greater_affixes=False,
        import_charms=True,
        import_seals=True,
        warn=lambda *_warning: None,
        unsafe_charms=unsafe_charms,
        unsafe_seals=unsafe_seals,
    )
    return charms, seals, unsafe_charms + unsafe_seals


def test_unreadable_charm_mod_keeps_the_charm_broadly() -> None:
    known = next(iter(GameCatalog().charm_affix_dict))
    charms, _, unsafe = _talismans(
        [{"type": "Charm", "key": "charm-key", "mods": [{"name": known}, {"name": "Unknown"}]}], [known]
    )
    assert unsafe == []
    assert charms[0].affix_pool == []
    rules = replace(LoadedRules.empty(), charm_filters={"p": [DynamicCharmFilterModel(root={"charm": charms[0]})]})
    charm = Item(item_type=ItemType.Charm, rarity=ItemRarity.Rare, power=800, affixes=[Affix(name="other")])
    assert FilterEvaluator(rules=rules).should_keep(charm).keep  # it may carry only the unreadable mod


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"type": "Charm", "key": "missing-key"}, "charm missing-key"),
        ({"type": "Charm", "key": "charm-key", "itemQuality": "Unique"}, "charm charm-key unique Charm"),
        ({"type": "Amulet", "key": "x"}, "talisman type amulet x"),
    ],
)
def test_unmappable_talisman_identity_is_unsafe(entry, expected) -> None:
    charms, seals, unsafe = _talismans([entry], [])
    assert (charms, seals, unsafe) == ([], [], [expected])
