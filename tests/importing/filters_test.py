import pytest

from src.game_data import WEAPON_TYPES, GameCatalog, ItemRarity, ItemType
from src.importing import DEFAULT_FILENAME_PARTS, FilenamePart, ImportOptions, ImportRequest, assemble_profile_file_name
from src.importing.filters import (
    create_item_affix_pool,
    create_seal_charm_filter,
    deduplicate_filters,
    fix_weapon_type,
    is_unique_like_rarity,
    resolve_unique_name,
    unique_filter_name,
    update_mingreateraffixcount,
)
from src.item import Affix, AffixType
from src.profiles import CharmFilterModel, ItemFilterModel, ProfileModel, to_yaml_str


def test_weapon_type_distinguishes_crossbow_from_bow() -> None:
    assert fix_weapon_type("Crossbow") == ItemType.Crossbow2H
    assert fix_weapon_type("Bow") == ItemType.Bow


def test_build_default_profile_file_name_maxroll() -> None:
    file_name = assemble_profile_file_name(
        source_name="maxroll", class_name="Spiritborn", build_header="Touch of Death", variant_name="Pit Push"
    )

    assert file_name == "maxroll_spiritborn_touch_of_death_pit_push"


def test_build_default_profile_file_name_d4builds_strips_title_suffix() -> None:
    file_name = assemble_profile_file_name(
        source_name="d4builds", class_name="Barbarian", build_header="Bash Build - D4Builds"
    )

    assert file_name == "d4builds_barbarian_bash_build"


def test_build_default_profile_file_name_d4builds_strips_spaced_title_suffix() -> None:
    file_name = assemble_profile_file_name(
        source_name="d4builds", class_name="Barbarian", build_header="Bash Build · D4 Builds"
    )

    assert file_name == "d4builds_barbarian_bash_build"


def test_build_default_profile_file_name_keeps_unknown_class_and_empty_variant() -> None:
    file_name = assemble_profile_file_name(
        source_name="mobalytics", class_name="Unknown", build_header="Whirlwind Leveling Barb", variant_name=""
    )

    assert file_name == "mobalytics_unknown_whirlwind_leveling_barb"


def test_build_default_profile_file_name_adds_season_and_strips_matching_header_marker() -> None:
    file_name = assemble_profile_file_name(
        source_name="d4builds",
        class_name="Paladin",
        season_number="12",
        build_header="Rob's Cpt. America (S12)",
        variant_name="Pit Push (Glasscannon)",
    )

    assert file_name == "d4builds_s12_paladin_robs_cpt_america_pit_push_glasscannon"


def test_build_default_profile_file_name_replaces_stale_season_marker_in_header() -> None:
    file_name = assemble_profile_file_name(
        source_name="maxroll", class_name="Sorcerer", season_number="12", build_header="S11 Crackling Energy Sorc"
    )

    assert file_name == "maxroll_s12_sorcerer_crackling_energy_sorc"


def test_build_default_profile_file_name_uses_selected_parts() -> None:
    file_name = assemble_profile_file_name(
        source_name="d4builds",
        class_name="Barbarian",
        season_number="12",
        build_header="Bash Build - D4Builds",
        variant_name="Pit Push",
        filename_parts=(FilenamePart.SOURCE, FilenamePart.BUILD_TITLE),
    )

    assert file_name == "d4builds_bash_build"


def test_build_default_profile_file_name_uses_unknown_for_selected_missing_class() -> None:
    file_name = assemble_profile_file_name(source_name="", class_name="", filename_parts=(FilenamePart.CLASS,))

    assert file_name == "unknown"


def test_build_default_profile_file_name_falls_back_when_no_parts_selected() -> None:
    file_name = assemble_profile_file_name(
        source_name="d4builds", class_name="Barbarian", build_header="Bash Build", filename_parts=()
    )

    assert file_name == "imported"


def test_import_config_defaults_to_all_filename_parts() -> None:
    request = ImportRequest("https://example.invalid", ImportOptions(import_greater_affixes=True))

    assert request.filename_parts == DEFAULT_FILENAME_PARTS


def test_import_config_normalizes_filename_parts() -> None:
    request = ImportRequest("https://example.invalid", ImportOptions(filename_parts=("source", "variant")))

    assert request.filename_parts == (FilenamePart.SOURCE, FilenamePart.VARIANT)


def test_unique_filter_name_adds_suffix_for_existing_filter_names() -> None:
    filter_name = unique_filter_name("Charm", [{"Charm": object()}, {"Charm2": object()}])

    assert filter_name == "Charm3"


def test_is_unique_like_rarity_handles_enum_and_string_values() -> None:
    assert is_unique_like_rarity(ItemRarity.Unique) is True
    assert is_unique_like_rarity(ItemRarity.Mythic) is True
    assert is_unique_like_rarity("unique") is True
    assert is_unique_like_rarity("mythic") is True
    assert is_unique_like_rarity(ItemRarity.Legendary) is False
    assert is_unique_like_rarity("legendary") is False
    assert is_unique_like_rarity(None) is False


def test_create_item_affix_pool_sets_expected_min_count_and_greater_flags() -> None:
    affixes = [Affix(name="armor", type=AffixType.greater), Affix(name="maximum_life")]

    unique_like_pool = create_item_affix_pool(affixes=affixes, unique_like=True)
    non_unique_pool = create_item_affix_pool(affixes=affixes, unique_like=False)

    assert unique_like_pool[0].min_count == 1
    assert non_unique_pool[0].min_count == 2  # never more than the listed affixes
    assert [affix.name for affix in unique_like_pool[0].count] == ["armor", "maximum_life"]
    assert unique_like_pool[0].count[0].want_greater is True
    assert unique_like_pool[0].count[1].want_greater is False


def test_to_yaml_str_sorts_aspect_upgrades_and_uses_block_style(mock_ini_loader) -> None:
    profile = ProfileModel(name="test", AspectUpgrades=["snowveiled", "accelerating"])

    yaml_str = to_yaml_str(profile, exclude_defaults=True, exclude={"name", "Sigils"})

    assert "aspect_upgrades:\n- accelerating\n- snowveiled\n" in yaml_str
    assert "aspect_upgrades: [" not in yaml_str


def test_deduplicate_filters() -> None:
    f1 = CharmFilterModel(set=["tal_rashas_threefold_way"])
    f2 = CharmFilterModel(set=["tal_rashas_threefold_way"])
    f3 = CharmFilterModel(set=["applied_alchemy"])

    filters = [f1, f2, f3]

    deduped = deduplicate_filters(filters)
    assert len(deduped) == 2
    assert "Charm(x2)" in deduped[0]
    assert deduped[0]["Charm(x2)"] == f1
    assert "Charm" in deduped[1] or "Charm2" in deduped[1]


def test_deduplicate_filters_supports_item_filters() -> None:
    f1 = ItemFilterModel(item_type=[ItemType.Ring])
    f2 = ItemFilterModel(item_type=[ItemType.Ring])
    f3 = ItemFilterModel(item_type=[ItemType.Amulet])

    deduped = deduplicate_filters([f1, f2, f3])

    assert len(deduped) == 2
    assert "Ring(x2)" in deduped[0]
    assert deduped[0]["Ring(x2)"] == f1
    assert "Amulet" in deduped[1]


def test_deduplicate_filters_names_unresolved_weapon_by_slot_hint() -> None:
    f1 = ItemFilterModel(item_type=WEAPON_TYPES)
    f2 = ItemFilterModel(item_type=[ItemType.Ring])

    deduped = deduplicate_filters([f1, f2], name_hints=["Dual-Wield Weapon 1", None])

    assert "Dual-Wield Weapon 1" in deduped[0]
    assert "Axe" not in deduped[0]
    assert "Ring" in deduped[1]


def test_deduplicate_filters_falls_back_to_axe_without_hint() -> None:
    f1 = ItemFilterModel(item_type=WEAPON_TYPES)

    deduped = deduplicate_filters([f1])

    assert "Axe" in deduped[0]


def test_to_yaml_str_preserves_paragon_aliases(mock_ini_loader) -> None:
    profile = ProfileModel(
        name="test",
        Paragon={
            "Name": "Build Name",
            "ParagonBoardsList": [
                [{"Name": "Starting Board", "Glyph": "glyph_name", "Rotation": 0, "Nodes": [False] * 441}]
            ],
        },
    )

    yaml_str = to_yaml_str(profile, exclude_defaults=True, exclude={"name", "Sigils"})

    assert "Paragon:" in yaml_str
    assert "ParagonBoardsList:" in yaml_str
    assert "Name: Build Name" in yaml_str


@pytest.mark.parametrize(
    ("resolved", "unresolved", "unique_like", "expected"),
    [(2, 0, False, 2), (4, 0, False, 3), (2, 2, False, 1), (1, 3, False, None), (0, 2, False, None)]
    + [(2, 0, True, 1), (2, 1, True, None)],
)
def test_item_pool_requires_only_what_imported_affixes_can_prove(resolved, unresolved, unique_like, expected):
    names = ["willpower", "maximum_life", "resistance_to_all_elements", "resource_generation"][:resolved]
    item_filter = ItemFilterModel(item_type=[ItemType.Helm])
    pool = create_item_affix_pool([Affix(name=name) for name in names], unique_like, unresolved_count=unresolved)
    item_filter.affix_pool = pool
    update_mingreateraffixcount(item_filter, require_gas=True)  # a broadened rule has no pool to index
    assert ([group.min_count for group in pool] or [None]) == [expected]


@pytest.mark.parametrize(("unresolved", "pool_size"), [(0, 1), (1, 0)])
def test_talisman_pool_is_dropped_once_any_listed_affix_is_unreadable(unresolved, pool_size) -> None:
    affixes = [Affix(name=next(iter(GameCatalog().charm_affix_dict)), type=AffixType.greater)]
    charm = create_seal_charm_filter(affixes, True, CharmFilterModel, unresolved_count=unresolved)
    assert len(charm.affix_pool) == pool_size
    assert charm.min_greater_affix_count == 1  # still implied by the readable greater affix


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Harlequin Crest", "harlequin_crest"), ("Tyrael's Might", "tyraels_might"), ("Future Unique", None), ("", None)],
)
def test_resolve_unique_name(label, expected) -> None:
    assert resolve_unique_name(label) == expected
