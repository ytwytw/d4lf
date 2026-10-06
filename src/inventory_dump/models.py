"""Lossless inventory observations, independent of filtering decisions."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from src.type_aliases import JsonObject


class ExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "md"
    TEXT = "txt"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class ScanProgress:
    stage: str
    location: str = ""
    scanned: int = 0
    failed: int = 0
    message: str = ""


@dataclass(frozen=True, slots=True)
class ScanResult:
    output_path: Path
    status: str
    item_count: int
    failed_count: int
    issues: tuple[str, ...] = ()
    unparsed_count: int = 0
    unverified_count: int = 0


@dataclass(frozen=True, slots=True)
class Location:
    scope: str
    page: str
    slot: str
    center: tuple[int, int]
    row: int | None = None
    column: int | None = None

    @property
    def label(self) -> str:
        return f"{self.scope}/{self.page}/{self.slot}"


@dataclass(slots=True)
class ItemRecord:
    location: Location
    favorite: bool | None = None
    junk: bool | None = None
    observed_at: str = field(default_factory=utc_now)
    attempts: int = 0
    status: str = "pending"
    raw_tts: list[str] = field(default_factory=list)
    raw_events: list[JsonObject] = field(default_factory=list)
    normalized_tts: list[str] = field(default_factory=list)
    parsed: JsonObject | None = None
    observed_fields: JsonObject | None = None
    error: str | None = None
    capture_complete: bool = False
    capture_source: str | None = None
    raw_sequence_start: int | None = None
    raw_sequence_end: int | None = None
    truncated: bool = False
    favorite_evidence: list[JsonObject] = field(default_factory=list)
    # Visual guesses stay unverified; only an explicit current-title TTS marker sets ``junk``.
    junk_evidence: list[JsonObject] = field(default_factory=list)
    occupancy_evidence: JsonObject | None = None
    # Export-only text restored around a shared-framer trace; parser input stays unchanged.
    raw_reconstruction: JsonObject | None = None


@dataclass(slots=True)
class ScopeRecord:
    kind: str
    page: str
    status: str = "pending"
    slots: int = 0
    empty_slots: int = 0
    observed_items: int = 0
    errors: list[str] = field(default_factory=list)
    occupancy_settled: bool | None = None
    # Hovered locations without an item record: confirmed empty, or occupancy still unknown.
    empty_slot_evidence: list[JsonObject] = field(default_factory=list)
    unverified_slots: list[JsonObject] = field(default_factory=list)


@dataclass(slots=True)
class ScanDocument:
    locale: str
    app_version: str
    started_at: str = field(default_factory=utc_now)
    schema_version: int = 2
    game_build: str = "unknown"
    status: str = "running"
    finished_at: str | None = None
    scopes: list[ScopeRecord] = field(default_factory=list)
    items: list[ItemRecord] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return sum(
            item.status not in {"empty", "pending", "unverified"} and (not item.capture_complete or item.truncated)
            for item in self.items
        )

    @property
    def unparsed_count(self) -> int:
        return sum(item.capture_complete and item.status in {"unparsed", "parse_error"} for item in self.items)

    @property
    def unverified_count(self) -> int:
        return sum(len(scope.unverified_slots) for scope in self.scopes)
