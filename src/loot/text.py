"""Localized presentation for stable loot-filter match identifiers."""

from src.item import ASPECT_UPGRADES_LABEL, MYTHICS_ALWAYS_KEPT_LABEL, Dataloader
from src.localization import translate

_BUILTIN_PROFILE_MESSAGES = {
    ASPECT_UPGRADES_LABEL: "loot.section.aspect_upgrades",
    MYTHICS_ALWAYS_KEPT_LABEL: "loot.reason.mythics_always_kept",
    "Cosmetics": "loot.reason.cosmetics",
    "Mythic Charm": "loot.reason.mythic_charm",
    "Mythic Seal": "loot.reason.mythic_seal",
    "Mythic Sigil": "loot.reason.mythic_sigil",
    "Mythic Tribute": "loot.reason.mythic_tribute",
    "Sigils not filtered": "loot.reason.sigils_unfiltered",
    "Tributes not filtered": "loot.reason.tributes_unfiltered",
}


def match_profile_text(profile: str) -> str:
    """Translate only application-owned match labels, preserving user profile names."""
    if message_id := _BUILTIN_PROFILE_MESSAGES.get(profile):
        return translate(message_id, profile)
    suffix = f".{ASPECT_UPGRADES_LABEL}"
    if profile.endswith(suffix):
        return f"{profile.removesuffix(suffix)}.{translate('loot.section.aspect_upgrades')}"
    return profile


def affix_text(canonical_name: str) -> str:
    """Resolve a canonical affix ID through the active game locale catalog."""
    data = Dataloader()
    for catalog in (data.affix_dict, data.seal_affix_dict, data.charm_affix_dict):
        if localized_name := catalog.get(canonical_name):
            return localized_name
    return canonical_name
