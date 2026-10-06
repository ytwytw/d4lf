import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.game_data import GameCatalog, ItemType
from src.importing import ImportOptions, ImportRequest
from src.importing.maxroll.adapter import _extract_profile_variant
from src.importing.maxroll.data import _find_item_name, _has_explicit_affix_references, _merge_localized_data
from src.item import Affix

if TYPE_CHECKING:
    from src.type_aliases import JsonObject


def test_find_item_name_returns_none_when_both_records_are_unnamed() -> None:
    assert (
        _find_item_name(
            resolved_item={"id": "item-1"}, resolved_item_id="item-1", item_mapping={"item-1": {"type": "Helm"}}
        )
        is None
    )


def test_merge_localized_data_overlays_nested_records() -> None:
    mapping_data: JsonObject = {
        "items": {"item-1": {"type": "Helm", "magicType": 4}},
        "attributeDescriptions": {"old": "fallback"},
    }

    _merge_localized_data(
        mapping_data, {"items": {"item-1": {"name": "Harlequin Crest"}}, "attributeDescriptions": {"new": "localized"}}
    )

    assert mapping_data == {
        "items": {"item-1": {"type": "Helm", "magicType": 4, "name": "Harlequin Crest"}},
        "attributeDescriptions": {"old": "fallback", "new": "localized"},
    }


@pytest.mark.parametrize("raw", [None, {}, "", [None], [{}], [{"nid": True}], [{"nid": ""}]])
def test_incomplete_explicit_references_are_not_empty_affix_lists(raw) -> None:
    assert not _has_explicit_affix_references({"explicits": raw})


def test_missing_explicit_references_are_rejected_but_explicit_empty_list_is_valid() -> None:
    assert not _has_explicit_affix_references({"id": "planner-item"})
    assert _has_explicit_affix_references({"explicits": []})
    assert _has_explicit_affix_references({"explicits": [{"nid": 123}, {"nid": "affix-id"}]})


def test_live_incomplete_items_stay_broad_and_runeword_keeps_its_unique_identity(mocker, caplog) -> None:
    capture = json.loads((Path(__file__).parent / "data/minion_necromancer_s15.json").read_text(encoding="utf-8"))
    find_affixes = mocker.patch("src.importing.maxroll.slots._find_item_affixes", return_value=[Affix(name="armor")])
    variant = _extract_profile_variant(
        profile_data={"name": "Captured incomplete items", "items": {key: int(key) for key in capture["items"]}},
        items=capture["items"],
        mapping_data=capture["mapping_data"],
        class_name="Necromancer",
        build_header="Captured",
        request=ImportRequest(url=capture["source_url"]),
    )

    enigma, boots, shield = variant.affix_filters
    assert (enigma.item_type, [aspect.name for aspect in enigma.unique_aspect]) == ([ItemType.ChestArmor], ["enigma"])
    # Incomplete explicits: the wanted slots stay as visibly broad rules instead of disappearing.
    assert [(rule.item_type, rule.unique_aspect, rule.affix_pool) for rule in (boots, shield)] == [
        ([ItemType.Boots], [], []),
        ([ItemType.Shield], [], []),
    ]
    assert [charm.affix_pool for charm in variant.charm_filters] == [[]]
    assert variant.unsafe_slots == []
    find_affixes.assert_called_once()
    for item_id in ("Boots_Legendary_Generic_053", "1HShield_Legendary_Generic_001", "Talisman_Charm_Set_Necro_04_02"):
        assert f"Maxroll item {item_id} has missing or malformed explicits; keeping its slot broadly" in caplog.text


@pytest.mark.parametrize("magic_type", [0, 1, 2, 4, None])
def test_runeword_never_becomes_an_affix_only_filter_even_if_rarity_mapping_drifts(magic_type, mocker) -> None:
    find_affixes = mocker.patch("src.importing.maxroll.slots._find_item_affixes", return_value=[Affix(name="armor")])
    variant = _extract_profile_variant(
        profile_data={"items": {"chest": 1}},
        items={"1": {"id": "Runeword_Enigma", "explicits": [{"nid": 1}]}},
        mapping_data={"items": {"Runeword_Enigma": {"type": "ChestArmor", "magicType": magic_type, "name": "Enigma"}}},
        class_name="Necromancer",
        build_header="Test",
        request=ImportRequest(url="https://maxroll.gg/d4/planner/test#1"),
    )
    assert [[aspect.name for aspect in rule.unique_aspect] for rule in variant.affix_filters] == [["enigma"]]
    find_affixes.assert_called_once()


@pytest.mark.parametrize("item_type", ["ChestArmor", "Charm", "HoradricSeal"])
@pytest.mark.parametrize("magic_type", [2, 4])
def test_unknown_unique_cannot_become_an_affix_only_filter(
    item_type, magic_type, mock_ini_loader, mocker, caplog
) -> None:
    GameCatalog()
    find_affixes = mocker.patch("src.importing.maxroll.slots._find_item_affixes", return_value=[Affix(name="armor")])
    variant = _extract_profile_variant(
        profile_data={"items": {"slot": 1}},
        items={"1": {"id": "unknown", "explicits": [{"nid": 1}]}},
        mapping_data={
            "items": {"unknown": {"type": item_type, "magicType": magic_type, "name": "Unconfirmed Future Unique"}}
        },
        class_name="Necromancer",
        build_header="Test",
        request=ImportRequest(url="https://maxroll.gg/d4/planner/test#1"),
    )
    assert variant.affix_filters == variant.charm_filters == variant.seal_filters == []
    unsafe = variant.unsafe_slots + variant.unsafe_charms + variant.unsafe_seals
    assert unsafe == ["unique Unconfirmed Future Unique"]  # rejects the whole import
    find_affixes.assert_not_called()
    assert "Maxroll unique Unconfirmed Future Unique (unknown) is not in D4LF's item data" in caplog.text


@pytest.mark.parametrize("magic_type", [2, 4])
def test_known_unique_empty_affixes_survives_incomplete_neighbor(magic_type, mock_ini_loader, caplog) -> None:
    GameCatalog()
    variant = _extract_profile_variant(
        profile_data={"items": {"boots": 1, "helm": 2}},
        items={"1": {"id": "Boots_Legendary_Generic_053"}, "2": {"id": "known", "explicits": []}},
        mapping_data={
            "items": {"known": {"type": "Helm", "magicType": magic_type, "name": "Harlequin Crest"}},
            "affixes": {},
        },
        class_name="Necromancer",
        build_header="Test",
        request=ImportRequest(url="https://maxroll.gg/d4/planner/test#1", options=ImportOptions()),
    )
    assert len(variant.affix_filters) == 1
    kept = variant.affix_filters[0]
    assert kept.item_type == [ItemType.Helm]
    assert kept.unique_aspect[0].name == "harlequin_crest"
    assert kept.affix_pool == []
    # The boots have neither explicits nor mapping data, so their identity is unknown and the import is rejected.
    assert variant.unsafe_slots == ["item Boots_Legendary_Generic_053 (unknown item type)"]


@pytest.mark.parametrize("magic_type", [2, 4])
@pytest.mark.parametrize(
    ("item_type", "item_name", "canonical", "filter_field"),
    [
        ("Helm", "Harlequin Crest", "harlequin_crest", "affix_filters"),
        ("Charm", "Seed of Horazon", "seed_of_horazon", "charm_filters"),
        ("HoradricSeal", "Seal of the Diamond Mind", "seal_of_the_diamond_mind", "seal_filters"),
    ],
)
def test_known_unique_empty_list_keeps_crucible_normalization(
    magic_type, item_type, item_name, canonical, filter_field, mock_ini_loader
) -> None:
    variant = _extract_profile_variant(
        profile_data={"items": {"slot": 1}},
        items={"1": {"id": "known", "explicits": []}},
        mapping_data={
            "items": {"known": {"type": item_type, "magicType": magic_type, "name": f"{item_name} (Crucible)"}},
            "affixes": {},
        },
        class_name="Necromancer",
        build_header="Test",
        request=ImportRequest(url="https://maxroll.gg/d4/planner/test#1"),
    )
    filters = getattr(variant, filter_field)
    assert len(filters) == 1
    assert filters[0].unique_aspect[0].name == canonical
    assert filters[0].affix_pool == []
