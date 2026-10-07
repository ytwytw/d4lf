import logging
import re
from typing import TYPE_CHECKING

from src.game_data import ItemRarity, ItemType
from src.importing.affix_identity import normalize_affix_label, resolve_affix
from src.importing.conversion import as_string_keyed_mapping as _as_mapping
from src.importing.conversion import as_string_keyed_mapping_list as _as_mapping_list
from src.importing.conversion import as_text as _as_text
from src.importing.maxroll.constants import (
    SKILL_RANK_AFFIX_KEY_REGEX,
    SKILL_RANK_BONUS_FORMULAS,
    SKILL_RANK_DESC_LABEL_REGEX,
)
from src.item import Affix, AffixType

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from src.type_aliases import JsonValue


LOGGER = logging.getLogger(__name__)
LOGGER.propagate = True
SET_SEAL_DESC_REGEX = re.compile(r"\{c_set\}([^{}]+)\{/c\}:?(.+)$", re.DOTALL)
# MaxRoll spelling mistakes in set names, mapped to the in-game name.
SET_NAME_CORRECTIONS = {"Cain's Wild Lighting": "Cain's Wild Lightning"}


def _attribute_description_corrections(input_str: str) -> str:
    match input_str:
        case "On_Hit_Vulnerable_Proc_Chance":
            return "On_Hit_Vulnerable_Proc".lower()
        case "Movement_Bonus_On_Elite_Kill":
            return "Movement_Speed_Bonus_On_Elite_Kill".lower()
    return input_str.lower()


def _find_item_rarity(resolved_item_id: str, mapping_data: Mapping[str, JsonValue]) -> ItemRarity:
    # magic/rare = 0, legendary = 1, unique = 2, set = 3, mythic = 4
    items = _as_mapping(mapping_data.get("items"))
    item = _as_mapping(items.get(resolved_item_id))
    if item:
        rarity_id = item.get("magicType")
        if rarity_id == 1:
            return ItemRarity.Legendary
        if rarity_id == 2:
            return ItemRarity.Unique
        if rarity_id == 3:
            return ItemRarity.Set
        if rarity_id == 4:
            return ItemRarity.Mythic

    return ItemRarity.Common


def _as_text_mapping(value: JsonValue) -> Mapping[str, str]:
    mapping = _as_mapping(value)
    return {key: item for key, item in mapping.items() if isinstance(item, str)}


def _attr_desc_special_handling(affix_id: int | str) -> str:
    return "charm slot" if affix_id == 2609197 else ""


def _set_seal_description(affix_key: str, affix: Mapping[str, JsonValue]) -> str:
    """MaxRoll's own "<set>: <stat>" text for a set seal affix.

    Rebuilding these from attributes loses the stat (several Berserker's Crucible affixes all become
    "to Berserking") or mislabels it ("Fire Damage" read as "Fire Damage Multiplier").
    """
    if "Talisman" not in affix_key or "Set" not in affix_key:
        return ""
    match = SET_SEAL_DESC_REGEX.search(_as_text(affix.get("desc")))
    if not match:
        return ""
    set_name = SET_NAME_CORRECTIONS.get(match.group(1).strip(), match.group(1))
    return f"{set_name} {match.group(2)}"


def _find_item_affixes(
    mapping_data: Mapping[str, JsonValue],
    item_affixes: Sequence[Mapping[str, JsonValue]],
    item_type: ItemType,
    import_greater_affixes: bool = False,
    unresolved: list[str] | None = None,
) -> list[Affix]:
    """Resolve explicit affixes; filterable ones that cannot be resolved are appended to ``unresolved``."""
    res = []
    missing = unresolved if unresolved is not None else []
    affix_data = _as_mapping(mapping_data.get("affixes"))
    ui_strings = _as_mapping(mapping_data.get("uiStrings"))
    damage_type_labels = _as_text_mapping(ui_strings.get("damageType"))
    resource_type_labels = _as_text_mapping(ui_strings.get("resourceType"))
    attributes = _as_mapping(mapping_data.get("attributes"))
    attribute_descriptions = _as_text_mapping(mapping_data.get("attributeDescriptions"))
    skills = _as_mapping(mapping_data.get("skills"))
    for affix_id in item_affixes:
        affix_reference = _as_mapping(affix_id)
        reference_id = affix_reference.get("nid")
        for affix_key, raw_affix in affix_data.items():
            affix = _as_mapping(raw_affix)
            affix_value = affix.get("id")
            if affix_value != reference_id or not isinstance(affix_value, (int, str)):
                continue
            if affix.get("magicType") in [2, 4]:
                break
            attributes_list = _as_mapping_list(affix.get("attributes"))
            attr_desc = _attr_desc_special_handling(affix_value) or _set_seal_description(affix_key, affix)
            if not attr_desc:
                if not attributes_list:
                    continue
                attribute = attributes_list[0]
                attribute_name = _as_text(_as_mapping(attributes.get(str(attribute.get("id")))).get("name"))
                if attribute_name == "Set_Item_Count":
                    LOGGER.info("Skipping non-filterable MaxRoll set-count attribute '%s'", attribute_name)
                    break
                formula = attribute.get("formula")
                if isinstance(formula, str) and formula.startswith("SancAffix_"):
                    LOGGER.info(f"Skipping Transfiguration affix for item type '{item_type.value}'")
                    break
                if formula in [
                    "GearAffix_Resource_Per_Second",
                    "GearAffix_DamageType",
                    "GearAffix_DamageType_Greater",
                    "GearAffix_Resource_On_Kill",
                    "GearAffix_Resource_On_Kill_Warlock",
                    "GearAffix_Resistance_Single",
                ]:
                    if formula in ["GearAffix_DamageType", "GearAffix_DamageType_Greater"]:
                        param = str(attribute.get("param"))
                        if param in damage_type_labels:
                            attr_desc = damage_type_labels[param] + " Damage Multiplier"
                        elif "desc" in affix:
                            # These are seal affixes and we have to get the skill from the description
                            pattern = r"\{c_important\}([^{}]+)\{/c\}\s*(.+)$"
                            match = re.search(pattern, _as_text(affix.get("desc")))
                            if match:
                                attr_desc = f"{match.group(1)} {match.group(2)}"
                    elif formula == "GearAffix_Resistance_Single":
                        attr_desc = damage_type_labels[str(attribute["param"])] + " Resistance"
                    elif formula == "GearAffix_Resource_Per_Second":
                        param = str(attribute["param"])
                        attr_desc = resource_type_labels[param] + " Regeneration"
                    elif formula in ["GearAffix_Resource_On_Kill", "GearAffix_Resource_On_Kill_Warlock"]:
                        attr_desc = resource_type_labels[str(attribute["param"])] + " On Kill"
                elif "param" not in attribute:
                    attr_id = attribute["id"]
                    attr_obj = _as_mapping(attributes.get(str(attr_id)))
                    attr_name = _as_text(attr_obj.get("name"))
                    attr_desc = attribute_descriptions.get(_attribute_description_corrections(attr_name))
                    if not attr_desc:
                        LOGGER.warning(
                            f"Unable to map {attr_name} from MaxRoll data to an affix, skipping affix and please report a bug."
                        )
                        continue
                else:  # must be + to talent or skill
                    attr_param = attribute["param"]
                    for raw_skill in skills.values():
                        skill_data = _as_mapping(raw_skill)
                        if skill_data.get("id") == attr_param:
                            attr_desc = f"to {_as_text(skill_data.get('name'))}"
                            break
                    else:
                        attr_desc = _find_skill_rank_affix_description(
                            mapping_data=mapping_data, affix_key=affix_key, attribute=attribute
                        )

                if "Talisman" in affix_key and "Set" in affix_key:
                    LOGGER.warning(
                        f"We thought affix {attr_desc} was a seal-based affix activated by a set but we could not determine the set. The affix is skipped, please report a bug with a link to the build."
                    )
                    continue

            if not normalize_affix_label(attr_desc):
                LOGGER.warning(
                    f"We were unable to map an attribute on item type {item_type.value} to an affix. Please report a bug and include a link to the build, we are skipping that affix."
                )
                continue

            matched_name = resolve_affix(attr_desc, item_type)
            if matched_name is not None:
                affix_obj = Affix(name=matched_name)
                if import_greater_affixes and affix_id.get("greater") is True:
                    affix_obj.type = AffixType.greater
                res.append(affix_obj)
            elif (
                attributes_list
                and "formula" in attributes_list[0]
                and attributes_list[0]["formula"] == "InherentAffixAnyResist_Ring"
            ):
                LOGGER.info("Skipping InherentAffixAnyResist_Ring")
            else:
                LOGGER.error(f"Couldn't match {affix_id=}")
                missing.append(str(reference_id))
            break
        else:
            # No mapping entry produced a decision (unknown id, or an attribute that could not be mapped).
            missing.append(str(reference_id))
    return res


def _find_skill_rank_affix_description(
    mapping_data: Mapping[str, JsonValue], affix_key: str, attribute: Mapping[str, JsonValue]
) -> str:
    if attribute.get("formula") not in SKILL_RANK_BONUS_FORMULAS:
        return ""
    param = attribute.get("param")
    param_int = param if isinstance(param, int) and not isinstance(param, bool) else None
    if (label := _find_skill_rank_label_from_descriptions(mapping_data, param_int)) or (
        label := _find_skill_rank_label_from_affix_key(affix_key)
    ):
        return f"to {label} skills"
    return ""


def _find_skill_rank_label_from_descriptions(mapping_data: Mapping[str, JsonValue], param: int | None) -> str:
    if param is None:
        return ""
    for raw_affix in _as_mapping(mapping_data.get("affixes")).values():
        affix = _as_mapping(raw_affix)
        if not any(
            attr.get("formula") in SKILL_RANK_BONUS_FORMULAS and attr.get("param") == param
            for attr in _as_mapping_list(affix.get("attributes"))
        ):
            continue
        if match := SKILL_RANK_DESC_LABEL_REGEX.search(_as_text(affix.get("desc"))):
            return str(match.group(1))
    return ""


def _find_skill_rank_label_from_affix_key(affix_key: str) -> str:
    if "SkillRankBonus_AllSkills" in affix_key:
        return "all"
    if match := SKILL_RANK_AFFIX_KEY_REGEX.search(affix_key):
        label = match.group("label")
        if label == "Bludgeoning":
            return "combat"
        label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label)
        label = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", label)
        return " ".join(label.split())
    return ""


__all__ = [name for name in globals() if not name.startswith("__")]
