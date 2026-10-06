"""Conservative fusion of already acquired evidence, without UI or capture side effects."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from unicodedata import normalize

if TYPE_CHECKING:
    from src.type_aliases import JsonObject, JsonValue

type Source = Literal["raw_tts", "ocr", "template", "manual_annotation"]


@dataclass(frozen=True, slots=True)
class Identity:
    name: str | None
    item_type: str | None
    item_power: int | None


@dataclass(frozen=True, slots=True)
class CaptureContext:
    """A producer-issued hover correlation key, never inferred from an item name."""

    capture_id: str
    location: str
    sequence_start: int
    sequence_end: int


@dataclass(frozen=True, slots=True)
class Candidate:
    field: str
    value: JsonValue
    source: Source
    reference: str
    text: str = ""

    def as_json(self) -> JsonObject:
        return {
            "field": self.field,
            "value": self.value,
            "source": self.source,
            "reference": self.reference,
            "text": self.text,
        }


def _identity_text(value: str | None) -> str | None:
    # Normalize typography only. Do not silently turn OCR's 開 into 00 or fuzzy-match names.
    return (re.sub(r"\s+", "", normalize("NFKC", value)) or None) if value else None


def compare_identity(tts: Identity, visual: Identity) -> JsonObject:
    """Same names are insufficient: a seal and an equipment item may share a title."""
    comparisons: JsonObject = {}
    for field, left, right in (
        ("name", _identity_text(tts.name), _identity_text(visual.name)),
        ("item_type", _identity_text(tts.item_type), _identity_text(visual.item_type)),
        ("item_power", tts.item_power, visual.item_power),
    ):
        comparisons[field] = "unknown" if left is None or right is None else "match" if left == right else "mismatch"
    status = (
        "mismatch"
        if "mismatch" in comparisons.values()
        else "unknown"
        if "unknown" in comparisons.values()
        else "content_consistent"
    )
    return {"status": status, "fields": comparisons}


def _same_capture(left: CaptureContext | None, right: CaptureContext | None) -> bool:
    return (
        left is not None
        and right is not None
        and left == right
        and bool(left.capture_id.strip())
        and bool(left.location.strip())
        and 0 < left.sequence_start <= left.sequence_end
    )


def fuse_evidence(
    *,
    tts_identity: Identity,
    visual_identity: Identity,
    candidates: list[Candidate],
    tts_context: CaptureContext | None = None,
    visual_context: CaptureContext | None = None,
) -> JsonObject:
    """Keep TTS primary, preserve conflicts and require association before adding visual fields.

    A context is supplied by the capture producer. Equality is a necessary association check,
    not proof that the producer captured the right image. Semantic identity is checked separately.
    Historical bundles lack original event bounds, so retain their visual results as evidence only.
    """
    identity = compare_identity(tts_identity, visual_identity)
    association = _same_capture(tts_context, visual_context)
    can_fuse = association and identity["status"] == "content_consistent"
    fields: JsonObject = {}
    for field in dict.fromkeys(candidate.field for candidate in candidates):
        all_candidates = [candidate for candidate in candidates if candidate.field == field]
        automatic = [candidate for candidate in all_candidates if candidate.source != "manual_annotation"]
        tts = [candidate for candidate in automatic if candidate.source == "raw_tts" and candidate.value is not None]
        visual = [candidate for candidate in automatic if candidate.source != "raw_tts" and candidate.value is not None]
        usable = tts + visual if can_fuse else tts
        selected = usable[0] if usable else None
        conflict = bool(selected and any(candidate.value != selected.value for candidate in usable))
        # Two disagreeing TTS values are also a conflict, never a silent last-write-wins result.
        fields[field] = {
            "value": selected.value if selected else None,
            "source": selected.source if selected else None,
            "reference": selected.reference if selected else None,
            "status": "conflict" if conflict else "observed" if selected else "unknown",
            "evidence": [candidate.as_json() for candidate in all_candidates],
        }
    return {
        "schema_version": 1,
        "mode": "offline_experiment",
        "identity": identity,
        "capture_association": "matching_context" if association else "unverified",
        "visual_fusion": "eligible" if can_fuse else "withheld",
        "fields": fields,
        "limitations": [
            "Missing evidence stays unknown; visible empty sockets do not establish a total socket count.",
            "Manual annotations are retained separately and never selected as automatic output.",
            "Identity agreement does not establish complete tooltip, scroll, or hidden-state coverage.",
            "Template scores are similarity scores, not calibrated probabilities of semantic correctness.",
        ],
    }
