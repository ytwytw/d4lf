"""Importer affix identity: exact labels after format normalization; unknown or ambiguous text stays unresolved."""

import pytest
import rapidfuzz

from src.game_data import ItemType
from src.importing import affix_identity
from src.importing.affix_identity import normalize_affix_label, resolve_affix, resolve_seal_affix
from src.importing.source_locale import source_affix_dict_for_item_type
from src.perception import closest_match


@pytest.fixture
def labels(monkeypatch):
    # Replace the English source labels the resolver indexes.
    def use(mapping: dict[str, str]) -> None:
        monkeypatch.setattr(affix_identity, "source_affix_dict_for_item_type", lambda *_args: mapping)
        affix_identity._exact_index.cache_clear()

    yield use
    affix_identity._exact_index.cache_clear()


@pytest.mark.parametrize(
    ("text", "item_type", "expected"),
    [
        ("+[1,226 - 1,450] Maximum Life", ItemType.Ring, "maximum_life"),
        ("maximum_life", ItemType.Ring, "maximum_life"),
        ("x[{value}*100|%|] Vulnerable Damage Multiplier", ItemType.Ring, "vulnerable_damage_multiplier"),
        ("+[{value}||] Maximum Evade |4Charge:Charges;", ItemType.Ring, "maximum_evade_charges"),
        (
            "{c_label}Lucky Hit:{/c} Up to a 15% Chance to Restore +[{value}||] Primary Resource",
            ItemType.Ring,
            "lucky_hit_up_to_a_chance_to_restore_primary_resource",
        ),
        (
            "+[{value}*100|%|] Bonus Kill Experience ([{value}*10|1%|] at level 70)",
            ItemType.Charm,
            "bonus_kill_experience",
        ),
        ("Damage (while Berserking)", ItemType.Ring, "damage_while_berserking"),  # words in parentheses count
        ("Damage (vs Bosses)", ItemType.Ring, None),  # an unknown qualifier never shortens to "damage"
        ("Damage [Elites]", ItemType.Ring, None),
        ("+10% Damage (2 second cooldown)", ItemType.Ring, None),  # a value-bearing qualifier with meaning
        ("{if:IsMythic}Mythic{else}Normal{/if} Damage", ItemType.Ring, None),  # template logic is not markup
        ("Damage [while Berserking for 5 seconds]", ItemType.Ring, None),  # a number does not make words a value
        ("Damage [vs Bosses|Elites]", ItemType.Ring, None),  # nor does a "|"
        ("Damage [Bosses||]", ItemType.Ring, None),  # a plain word is not a maxroll attribute placeholder
        ("+[5%] Damage", ItemType.Ring, "damage"),  # numeric-only brackets are values
        ("[11.0 - 15.0]% Resource Generation", ItemType.Ring, "resource_generation"),
        ("+20.0%[x] Vulnerable Damage", ItemType.Ring, "vulnerable_damage"),
        ("Dark Pact: +12% Non-Physical Damage", ItemType.HoradricSeal, "dark_pact_nonphysical_damage"),
        ("+12% Total Armor", ItemType.Ring, "total_armor"),  # not the flat "Armor" affix
        ("Totally New Season Stat", ItemType.Ring, None),
        ("Maximum Lif", ItemType.Ring, None),
        ("to Dual Wield Skills", ItemType.Ring, None),
        ("to All Skills", ItemType.HoradricSeal, None),  # an equipment affix; seals only have "Mastery to All Skills"
        ("+25%", ItemType.Ring, None),
    ],
)
def test_resolve_affix_accepts_only_an_exact_label_or_key(text, item_type, expected) -> None:
    assert resolve_affix(text, item_type) == expected


@pytest.mark.parametrize(
    ("text", "item_type"),
    [
        ("totally new season stat", ItemType.Ring),
        ("to dual wield skills", ItemType.Ring),
        ("to shock skills", ItemType.HoradricSeal),
        ("can equip more unique charm", ItemType.HoradricSeal),
    ],
)
def test_text_the_old_similarity_match_assigned_to_another_affix_is_now_unresolved(text, item_type) -> None:
    source_labels = source_affix_dict_for_item_type(item_type, "enUS")
    invented = closest_match(text, source_labels)  # what the importers did before: nearest label at any distance
    assert invented is not None
    assert source_labels[invented] != text
    assert resolve_affix(text, item_type) is None


def test_text_shared_by_two_affixes_is_ambiguous_and_unresolved(labels) -> None:
    labels({"fire_damage": "fire damage", "fire_damage_legacy": "Fire Damage", "armor": "armor"})
    assert resolve_affix("+10% Fire Damage", ItemType.Ring) is None
    assert resolve_affix("fire_damage_legacy", ItemType.Ring) == "fire_damage_legacy"  # its key is still unique
    assert resolve_affix("+100 Armor", ItemType.Ring) == "armor"


def test_empty_catalog_resolves_nothing_where_the_old_matcher_failed(labels) -> None:
    labels({})
    assert resolve_affix("Maximum Life", ItemType.Ring) is None
    assert resolve_seal_affix("Maximum Life", "survival") is None
    with pytest.raises(ValueError, match="not enough values"):
        closest_match("maximum life", {})


@pytest.mark.parametrize(
    ("text", "guessed_set", "expected"),
    [
        ("Maximum Resolve", "arms_of_arreat", "arms_of_arreat_maximum_resolve"),
        ("Cooldown Reduction", "arms_of_arreat", "cooldown_reduction"),
        ("Habacalva's Cauldron Fire Damage", None, "habacalvas_cauldron_fire_damage"),  # the source names the set
        (
            (
                "{c_set}Berserker's Crucible{/c}:\r\n+{c_number}[Power_Duration_Bonus_Pct(213812)*100|%|]{/c}"
                " {c_important}Berserking{/c} duration"
            ),
            None,
            "berserkers_crucible_berserking_duration",
        ),
        (
            (
                "{c_set}Legacy of the Sightless{/c}:\r\n+{c_number}[MaxStacks(2466372)||]{/c} Maximum"
                " {c_important}Overpower{/c} Stacks"
            ),
            None,
            "legacy_of_the_sightless_maximum_overpower_stacks",
        ),
        (
            "+5% Bonus Kill Experience (5% at level 70)",
            "practiced_technique",
            "practiced_technique_bonus_kill_experience_(_at_level_)",
        ),
        ("Maximum Resolve", None, None),  # two sets carry it and there is no guess
        ("Maximum Resolve", "unknown_set", None),
        ("Maximum Life", "flesh_of_abaddon", None),  # a generic and a set affix share the text
        ("Resolve", "arms_of_arreat", None),
    ],
)
def test_resolve_seal_affix_tries_the_guessed_set_with_exact_labels(text, guessed_set, expected) -> None:
    assert resolve_seal_affix(text, guessed_set) == expected


def test_word_overlap_the_old_set_matcher_accepted_is_not_identity() -> None:
    label = source_affix_dict_for_item_type(ItemType.HoradricSeal, "enUS")["arms_of_arreat_maximum_resolve"]
    assert rapidfuzz.fuzz.token_set_ratio("resolve", label) >= 50  # the old acceptance threshold
    assert resolve_seal_affix("Resolve", "arms_of_arreat") is None


def test_normalization_drops_formatting_and_value_qualifiers_but_keeps_words() -> None:
    assert (
        normalize_affix_label("Berserker’s Crucible:\r\n+{c_number}[x]12.5%{/c} Damage") == "berserkers crucible damage"
    )
    assert normalize_affix_label("Bul-Kathos' Pride (while Berserking)") == "bulkathos pride while berserking"


@pytest.mark.parametrize("item_type", [ItemType.Ring, ItemType.HoradricSeal, ItemType.Charm])
def test_every_english_label_names_exactly_its_own_affix(item_type) -> None:
    source_labels = source_affix_dict_for_item_type(item_type, "enUS")
    assert [name for name, label in source_labels.items() if resolve_affix(label, item_type) != name] == []
