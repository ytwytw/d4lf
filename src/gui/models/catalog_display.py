from collections.abc import Mapping

from src.config.loader import IniConfigLoader
from src.dataloader import Dataloader
from src.gui.i18n import translate
from src.item.data.item_type import ItemType


def current_catalog() -> Dataloader:
    """Return catalog data for the configured UI locale."""
    catalog = Dataloader()
    configured_locale = IniConfigLoader().general.language
    if catalog.grammar.locale != configured_locale:
        catalog.load_data()
    return catalog


def item_type_display_name(item_type: ItemType | str) -> str:
    catalog = current_catalog()
    if isinstance(item_type, ItemType):
        canonical = item_type.name
        fallback = item_type.value
    else:
        canonical = catalog.resolve_item_type(item_type) or item_type.removeprefix("ItemType.")
        member = ItemType.__members__.get(canonical)
        fallback = member.value if member is not None else item_type
    return catalog.item_types_dict.get(canonical) or fallback


def aspect_display_name(canonical: str) -> str:
    return current_catalog().aspect_dict.get(canonical) or canonical.replace("_", " ")


def unique_display_name(canonical: str) -> str:
    metadata = current_catalog().aspect_unique_dict.get(canonical)
    if isinstance(metadata, Mapping):
        display_name = metadata.get("display_name")
        if isinstance(display_name, str) and display_name:
            return display_name
    return canonical.replace("_", " ")


def set_display_name(canonical: str) -> str:
    return current_catalog().set_dict.get(canonical) or canonical.replace("_", " ")


def resolve_aspect_canonical(value: str) -> str | None:
    catalog = current_catalog()
    return catalog.resolve_aspect(value) or (value if value in catalog.aspect_dict else None)


def resolve_unique_canonical(value: str) -> str | None:
    catalog = current_catalog()
    return catalog.resolve_unique(value) or (value if value in catalog.aspect_unique_dict else None)


def catalog_group_label(source: str) -> str:
    return translate(source, locale=current_catalog().grammar.locale)
