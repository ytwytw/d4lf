from src.importing import ImportOptions
from src.importing.d2core.catalog import D2CoreCatalog
from src.importing.d2core.extraction import extract_d2core_variant
from src.item import Dataloader, ItemType


def _catalog() -> D2CoreCatalog:
    return D2CoreCatalog(
        build_version="72698",
        affix_aliases={
            "S04_CoreStat_Intelligence": ("Intelligence",),
            "X2_Armor_Greater": ("Armor",),
            "S04_CooldownReductionCDR": ("Cooldown Reduction",),
            "Tempered_Generic_LifeMax_Tier3": ("Maximum Life",),
            "Unknown": ("Brand New Season Mechanic Power",),
        },
        aspect_names={"AspectKey": "Aspect of the Untarnished Blaze", "TransfiguredKey": "Overheating Aspect"},
        unique_names={
            "UniqueKey": "Drognan's Anguish",
            "MythicKey": "Harlequin Crest",
            "UnknownUnique": "Not A Real Unique",
        },
    )


def test_extract_variant_maps_equipment_ga_aspects_uniques_and_mythics(mock_ini_loader) -> None:
    Dataloader()
    gear = [
        {
            "type": "legendary",
            "itemType": "ChestArmor",
            "key": "AspectKey",
            "transfiguredAspect": "TransfiguredKey",
            "mods": [
                {"name": "S04_CoreStat_Intelligence"},
                {"name": "X2_Armor_Greater", "greater": True},
                {"name": "Tempered_Generic_LifeMax_Tier3", "tempered": True},
                {"name": "Unknown"},
            ],
        },
        {"type": "uniqueItem", "itemType": "Ring", "key": "UniqueKey", "mods": [{"name": "S04_CooldownReductionCDR"}]},
        {"type": "mythic", "itemType": "Helm", "key": "MythicKey", "mods": []},
        {"type": "legendary", "itemType": "Charm", "mods": [{"name": "S04_CoreStat_Intelligence"}]},
        {"type": "legendary", "itemType": "UnknownType", "mods": [{"name": "S04_CoreStat_Intelligence"}]},
    ]
    options = ImportOptions(import_aspect_upgrades=True, import_greater_affixes=True, require_greater_affixes=True)

    variant = extract_d2core_variant(gear, _catalog(), options, name="Endgame")

    assert variant.name == "Endgame"
    assert variant.aspect_upgrade_filters == ["of_the_untarnished_blaze", "overheating"]
    assert [item.item_type[0] for item in variant.affix_filters] == [ItemType.ChestArmor, ItemType.Ring, ItemType.Helm]
    chest, ring, helm = variant.affix_filters
    assert [(affix.name, affix.want_greater) for affix in chest.affix_pool[0].count] == [
        ("armor", True),
        ("intelligence", False),
    ]
    assert chest.min_greater_affix_count == 1
    assert ring.unique_aspect[0].name == "drognans_anguish"
    assert ring.affix_pool[0].count[0].name == "cooldown_reduction"
    assert helm.unique_aspect[0].name == "harlequin_crest"
    assert helm.affix_pool == []


def test_extract_variant_skips_unresolved_unique_and_unknown_catalog_values(mock_ini_loader) -> None:
    Dataloader()
    gear = [{"type": "unique", "itemType": "Ring", "key": "UnknownUnique", "mods": [{"name": "Unknown"}]}]

    variant = extract_d2core_variant(gear, _catalog(), ImportOptions())

    assert variant.affix_filters == []
    assert variant.aspect_upgrade_filters == []


def test_extract_variant_does_not_mark_ga_when_option_is_disabled(mock_ini_loader) -> None:
    Dataloader()
    gear = [{"type": "legendary", "itemType": "Helm", "mods": [{"name": "X2_Armor_Greater", "greater": 1}]}]

    variant = extract_d2core_variant(gear, _catalog(), ImportOptions(import_greater_affixes=False))

    affix = variant.affix_filters[0].affix_pool[0].count[0]
    assert affix.name == "armor"
    assert not affix.want_greater
