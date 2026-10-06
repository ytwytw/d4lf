"""Read-only links from saved profiles to equipment identities."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.profiles import ItemFilterModel, ProfileDocumentStore, ProfileModel

if TYPE_CHECKING:
    from src.equipment_knowledge.catalog import EquipmentCatalog


@dataclass(frozen=True)
class ProfileEquipment:
    name: str
    unique_ids: frozenset[int]
    item_types: frozenset[str]
    unresolved: tuple[str, ...]


def equipment_for_profile(profile: ProfileModel, catalog: EquipmentCatalog) -> ProfileEquipment:
    ids: set[int] = set()
    types: set[str] = set()
    unresolved: list[str] = []
    for group in (*profile.affixes, *profile.charms, *profile.seals):
        for rule in group.root.values():
            if isinstance(rule, ItemFilterModel):
                types.update(item_type.value for item_type in rule.item_type)
            for aspect in rule.unique_aspect:
                found = catalog.resolve_unique(aspect.name)
                if found:
                    ids.update(found)
                else:
                    unresolved.append(aspect.name)
    return ProfileEquipment(profile.name, frozenset(ids), frozenset(types), tuple(sorted(set(unresolved))))


def load_profile_equipment(name: str, catalog: EquipmentCatalog) -> ProfileEquipment:
    store = ProfileDocumentStore.default()
    path = next(
        (
            path
            for path in sorted(store.profiles_dir.iterdir())
            if path.suffix.lower() in {".yaml", ".yml"} and name in {path.stem, path.stem.replace("_", " ")}
        ),
        None,
    )
    if path is None:
        msg = f"未找到已保存的 Profile：{name}"
        raise FileNotFoundError(msg)
    return equipment_for_profile(store.load(path).profile, catalog)
