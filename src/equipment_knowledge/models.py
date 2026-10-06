"""Versioned evidence models, separate from the runtime recognition catalog."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

type SourceRecord = dict[str, JsonValue]


class KnowledgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EquipmentEntry(KnowledgeModel):
    sno_id: int
    key: str
    canonical_name: str
    name_en: str
    name_zh: str | None = None
    item_type: str
    raw_en: SourceRecord
    raw_zh: SourceRecord | None = None


class AffixEntry(KnowledgeModel):
    sno_id: int
    key: str
    canonical_name: str | None = None
    name_en: str
    name_zh: str | None = None
    raw_en: SourceRecord
    raw_zh: SourceRecord | None = None


class ItemTypeEntry(KnowledgeModel):
    sno_id: int
    key: str
    canonical_name: str
    name_en: str
    name_zh: str | None = None


class KnowledgeData(KnowledgeModel):
    schema_version: int
    game_version: str
    snapshot_date: str
    source: str
    sources: tuple[SourceRecord, ...]
    limitations: tuple[str, ...]
    items: tuple[EquipmentEntry, ...]
    affixes: tuple[AffixEntry, ...]
    item_types: tuple[ItemTypeEntry, ...]
    native_affix_ids: dict[str, tuple[int, ...]] = Field(default_factory=dict)


class SnapshotPart(KnowledgeModel):
    path: str
    field: Literal["items", "affixes"]
    sha256: str
    records: int


class SnapshotIndex(KnowledgeData):
    parts: tuple[SnapshotPart, ...] = ()


class SnapshotChunk(KnowledgeModel):
    items: tuple[EquipmentEntry, ...] = ()
    affixes: tuple[AffixEntry, ...] = ()
