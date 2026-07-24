from src.dataloader import Dataloader
from src.gui.i18n import translate

_ASPECT_UPGRADES_LABEL = "AspectUpgrades"


def overlay_text(source: str, **values: str) -> str:
    """Translate built-in loot overlay text using the active game/UI locale."""
    return translate(source, **values)


def _display_unique_name(canonical: str) -> str:
    unique_data = Dataloader().aspect_unique_dict.get(canonical)
    if isinstance(unique_data, dict):
        display_name = unique_data.get("display_name")
        if isinstance(display_name, str) and display_name:
            return display_name
    return canonical


def display_profile_name(profile: object) -> str:
    """Translate built-in match reasons while preserving user profile names."""
    source = str(profile)
    translated = translate(source)
    if translated != source:
        return translated

    user_profile = getattr(profile, "user_profile", None)
    section_name = getattr(profile, "section_name", None)
    rule_name = getattr(profile, "rule_name", None)
    if isinstance(user_profile, str) and isinstance(section_name, str) and isinstance(rule_name, str):
        translated_section = translate(section_name)
        if translated_section != section_name:
            return f"{user_profile}.{translated_section}.{rule_name}"

    unique_name = getattr(profile, "unique_name", None)
    if isinstance(user_profile, str) and isinstance(unique_name, str) and translate("Unique") != "Unique":
        return f"{user_profile}.{_display_unique_name(unique_name)}"

    if source.endswith(_ASPECT_UPGRADES_LABEL):
        prefix = source[: -len(_ASPECT_UPGRADES_LABEL)]
        return f"{prefix}{translate(_ASPECT_UPGRADES_LABEL)}"
    return source


def display_affix_name(canonical: str) -> str:
    """Return the active locale's display label for a matched canonical affix."""
    catalog = Dataloader()
    return (
        catalog.affix_dict.get(canonical)
        or catalog.charm_affix_dict.get(canonical)
        or catalog.seal_affix_dict.get(canonical)
        or canonical
    )
