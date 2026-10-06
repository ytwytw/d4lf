"""Offline knowledge queries with explicit, verified native-filter mappings."""

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from src.equipment_knowledge.models import (
    AffixEntry,
    EquipmentEntry,
    ItemTypeEntry,
    KnowledgeData,
    SnapshotChunk,
    SnapshotIndex,
)


def canonical_name(text: str) -> str:
    return text.strip().casefold().replace("'", "").replace("’", "").replace(",", "").replace(" ", "_")


@dataclass(frozen=True)
class EquipmentCatalog:
    data: KnowledgeData

    @property
    def game_version(self) -> str:
        return self.data.game_version

    @property
    def source(self) -> str:
        return self.data.source

    @property
    def items(self) -> tuple[EquipmentEntry, ...]:
        return self.data.items

    @property
    def affixes(self) -> tuple[AffixEntry, ...]:
        return self.data.affixes

    @property
    def item_types(self) -> tuple[ItemTypeEntry, ...]:
        return self.data.item_types

    def resolve_unique(self, canonical: str) -> tuple[int, ...]:
        query = canonical_name(canonical)
        entries = [
            item
            for item in self.items
            if query
            in {
                canonical_name(item.canonical_name),
                canonical_name(item.key),
                canonical_name(item.name_en),
                canonical_name(item.name_zh or ""),
            }
        ]
        # A translated name shared by unrelated identities is not an identity proof.
        if len({entry.canonical_name for entry in entries}) > 1:
            return ()
        return tuple(sorted({item.sno_id for item in entries}))

    def resolve_affix(self, canonical: str) -> tuple[int, ...]:
        return self.data.native_affix_ids.get(canonical_name(canonical), ())

    def resolve_item_type(self, canonical: str) -> tuple[int, ...]:
        query = canonical_name(canonical)
        entries = [
            item
            for item in self.item_types
            if query
            in {
                canonical_name(item.canonical_name),
                canonical_name(item.key),
                canonical_name(item.name_en),
                canonical_name(item.name_zh or ""),
            }
        ]
        if len({entry.canonical_name for entry in entries}) > 1:
            return ()
        return tuple(sorted({item.sno_id for item in entries}))

    def search(self, query: str = "", item_type: str = "") -> tuple[EquipmentEntry, ...]:
        query = query.strip().casefold()
        return tuple(
            item
            for item in self.items
            if (not item_type or item.item_type == item_type)
            and (
                not query
                or query
                in " ".join((
                    item.name_en,
                    item.name_zh or "",
                    item.key,
                    item.canonical_name,
                    str(item.sno_id),
                )).casefold()
            )
        )

    def affixes_for_key(self, key: str) -> tuple[AffixEntry, ...]:
        return tuple(affix for affix in self.affixes if affix.key == key)


def catalog_path() -> Path:
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return root / "assets" / "equipment_knowledge" / "catalog-73552.json"


def load_catalog(path: Path | None = None) -> EquipmentCatalog:
    path = path or catalog_path()
    index = SnapshotIndex.model_validate_json(path.read_text(encoding="utf-8"))
    items, affixes = list(index.items), list(index.affixes)
    for part in index.parts:
        if Path(part.path).name != part.path:
            msg = "Knowledge snapshot parts must be sibling files"
            raise ValueError(msg)
        content = (path.parent / part.path).read_bytes()
        if hashlib.sha256(content).hexdigest() != part.sha256:
            msg = f"Knowledge snapshot checksum mismatch: {part.path}"
            raise ValueError(msg)
        chunk = SnapshotChunk.model_validate_json(content)
        entries = chunk.items if part.field == "items" else chunk.affixes
        if len(entries) != part.records:
            msg = f"Knowledge snapshot count mismatch: {part.path}"
            raise ValueError(msg)
        items.extend(chunk.items)
        affixes.extend(chunk.affixes)
    data = KnowledgeData.model_validate({**index.model_dump(exclude={"parts"}), "items": items, "affixes": affixes})
    if data.schema_version != 1:
        msg = f"Unsupported equipment knowledge schema: {data.schema_version}"
        raise ValueError(msg)
    if len({(item.key, item.sno_id) for item in data.items}) != len(data.items):
        msg = "Duplicate equipment identities in knowledge snapshot"
        raise ValueError(msg)
    return EquipmentCatalog(data)
