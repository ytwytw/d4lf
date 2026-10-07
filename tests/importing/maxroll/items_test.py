import logging
from typing import TYPE_CHECKING

import pytest

from src.game_data import GameCatalog, ItemType
from src.importing.maxroll.items import _attribute_description_corrections, _find_item_affixes

if TYPE_CHECKING:
    from src.type_aliases import JsonObject


def test_maxroll_item_text_correction_is_case_normalized() -> None:
    assert _attribute_description_corrections("Damage") == "damage"


def test_find_item_affixes_skips_set_count_attribute_at_info_level(caplog) -> None:
    mapping_data = {
        "affixes": {
            "HellfireTorch_Necro_05": {
                "id": 1,
                "magicType": 3,
                "attributes": [{"id": 828, "param": 2297198}],
                "desc": "+1 Set count to Rathma's Waking Touch.",
            }
        },
        "attributes": {"828": {"name": "Set_Item_Count"}},
        "skills": {},
    }

    with caplog.at_level(logging.INFO, logger="src.importing.maxroll.items"):
        affixes = _find_item_affixes(mapping_data=mapping_data, item_affixes=[{"nid": 1}], item_type=ItemType.Amulet)

    assert affixes == []
    assert any(record.levelno == logging.INFO and "Set_Item_Count" in record.message for record in caplog.records)
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_find_item_affixes_resolves_skill_rank_category_from_affix_key() -> None:
    mapping_data = {
        "affixes": {
            "X2_SkillRankBonus_Sorc_Category_Shock": {
                "id": 1,
                "magicType": 0,
                "attributes": [{"id": 1155, "param": 332737186, "formula": "GearAffix_SkillRankBonus_1to2"}],
            }
        },
        "skills": {},
    }

    affixes = _find_item_affixes(mapping_data=mapping_data, item_affixes=[{"nid": 1}], item_type=ItemType.Amulet)

    assert [affix.name for affix in affixes] == ["to_shock_skills"]


def test_find_item_affixes_resolves_skill_rank_category_from_related_description() -> None:
    mapping_data = {
        "affixes": {
            "Unknown_SkillRankBonus": {
                "id": 1,
                "magicType": 0,
                "attributes": [{"id": 1155, "param": 1856650534, "formula": "GearAffix_SkillRankBonus"}],
            },
            "Talisman_SealAffix_Set_Rogue_05_UltimateSkillRanks": {
                "id": 2,
                "magicType": 1,
                "attributes": [{"id": 1155, "param": 1856650534, "formula": "GearAffix_SkillRankBonus"}],
                "desc": "+{c_number}[Skill_Rank_Skill_Tag_Bonus(1856650534)||]{/c} {c_important}Ultimate{/c} Skills",
            },
        },
        "skills": {},
    }

    affixes = _find_item_affixes(mapping_data=mapping_data, item_affixes=[{"nid": 1}], item_type=ItemType.Amulet)

    assert [affix.name for affix in affixes] == ["to_ultimate_skills"]


@pytest.mark.parametrize(
    ("affix_key", "attribute"),
    [
        ("X2_Transfiguration_DamageTypePercent_Fire", {"id": 255, "param": 1, "formula": "SancAffix_10%"}),
        ("X2_Transfiguration_AttackSpeed", {"id": 221, "formula": "SancAffix_10%"}),
    ],
)
def test_find_item_affixes_skips_transfiguration_affixes(affix_key, attribute, caplog) -> None:
    GameCatalog()
    mapping_data = {"affixes": {affix_key: {"id": 1, "magicType": 0, "attributes": [attribute]}}, "skills": {}}

    with caplog.at_level(logging.INFO):
        affixes = _find_item_affixes(mapping_data=mapping_data, item_affixes=[{"nid": 1}], item_type=ItemType.Helm)

    assert affixes == []
    assert "Skipping Transfiguration affix" in caplog.messages[0]


def test_find_item_affixes_reports_unreadable_filterable_affixes_only(caplog) -> None:
    GameCatalog()
    mapping_data = {
        "affixes": {
            "X2_SkillRankBonus_Sorc_Category_Shock": {
                "id": 1,
                "magicType": 0,
                "attributes": [{"id": 1155, "param": 1, "formula": "GearAffix_SkillRankBonus_1to2"}],
            },
            "Unmappable": {"id": 2, "magicType": 0, "attributes": []},
            "Implicit": {"id": 3, "magicType": 2, "attributes": []},
            "Sanctified": {"id": 4, "magicType": 0, "attributes": [{"id": 221, "formula": "SancAffix_10%"}]},
        },
        "skills": {},
    }
    unresolved: list[str] = []
    affixes = _find_item_affixes(
        mapping_data=mapping_data,
        item_affixes=[{"nid": nid} for nid in (1, 2, 3, 4, 99)],
        item_type=ItemType.Amulet,
        unresolved=unresolved,
    )
    assert [affix.name for affix in affixes] == ["to_shock_skills"]
    assert unresolved == ["2", "99"]  # implicit and sanctified entries are deliberately not filterable


def _set_seal(nid: int, attribute: JsonObject, set_name: str, stat: str) -> JsonObject:
    desc = f"{{c_set}}{set_name}{{/c}}:\r\n+{{c_number}}[Affix_Value_1*100|%|]{{/c}} {stat}"
    return {"id": nid, "magicType": 1, "attributes": [attribute], "desc": desc}


def test_set_seal_affixes_are_read_from_the_maxroll_description() -> None:
    berserking: JsonObject = {"id": 1, "param": 213812, "formula": "SealAffix_Berserk_Duration"}
    mapping_data: JsonObject = {
        "affixes": {
            "Talisman_SealAffix_Set_Barbarian_02_BerserkDamage": _set_seal(
                1,
                {**berserking, "formula": "SealAffix_Damage_WhileBerserk"},
                "Berserker's Crucible",
                "Damage while Berserking",
            ),
            "Talisman_SealAffix_Set_Barbarian_02_BerserkDuration": _set_seal(
                2, berserking, "Berserker's Crucible", "{c_important}Berserking{/c} duration"
            ),
            "Talisman_SealAffix_Set_Spiritborn_01_WeakenedDamage": _set_seal(
                3, {"id": 2, "formula": "GearAffix_DamageType"}, "Balazan's Bite", "Damage to Weakened Enemies"
            ),
            "Talisman_SealAffix_Set_Sorcerer_03_MovementSpeed": _set_seal(
                4, {"id": 3}, "Cain's Wild Lighting", "Movement Speed"
            ),
        },
        "skills": {"berserking": {"id": 213812, "name": "Berserking"}},
    }
    affixes = _find_item_affixes(mapping_data, [{"nid": nid} for nid in (1, 2, 3, 4)], ItemType.HoradricSeal)
    # Before: both Berserking affixes became "to Berserking" (one identity), and the damage-type affix without a
    # param raised KeyError, failing the whole import.
    assert [affix.name for affix in affixes] == [
        "berserkers_crucible_damage_while_berserking",
        "berserkers_crucible_berserking_duration",
        "balazans_bite_damage_to_weakened_enemies",
        "cains_wild_lightning_movement_speed",
    ]
