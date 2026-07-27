"""Localization helpers that preserve stable settings values."""

from typing import TYPE_CHECKING

from src.localization import translate
from src.settings.models import SettingsCategory

if TYPE_CHECKING:
    import enum


def category_label(category: SettingsCategory) -> str:
    return translate(f"settings.category.{category.name.lower()}", str(category))


def category_group_title(category: SettingsCategory) -> str:
    if category is SettingsCategory.HOTKEYS:
        return translate("settings.group.hotkeys")
    if category is SettingsCategory.ADVANCED:
        return translate("settings.group.advanced")
    return category_label(category)


def field_title(section: str, key: str, default: str) -> str:
    return translate(f"settings.field.{section}.{key}.title", default)


def field_description(section: str, key: str, default: str) -> str:
    return translate(f"settings.field.{section}.{key}.description", default)


def option_label(value: enum.StrEnum) -> str:
    enum_name = type(value).__name__
    return translate(f"settings.option.{enum_name}.{value}", str(value))


def option_labels(values: list[enum.StrEnum]) -> dict[str, str]:
    return {str(value): option_label(value) for value in values}
