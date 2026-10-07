"""Decide what a hover proved: an item frame, item text, an empty slot, or unknown occupancy."""

from typing import TYPE_CHECKING

from src.inventory_dump.observations import ambient_only, item_lines, observe_favorite, observe_junk, slot_labels

if TYPE_CHECKING:
    from src.inventory_dump.models import ItemRecord
    from src.perception import ItemTraceSnapshot, RawTtsEvent

OCCUPIED_TIMEOUT = 2.5
VISUALLY_EMPTY_TIMEOUT = 1.2


def attempt_timeouts(expected_occupied: bool | None) -> tuple[float, ...]:
    """Return the per-hover bounds; every slot is hovered twice before silence is interpreted.

    A hover can produce no TTS at all (seen live on occupied slots), so a visually empty slot only
    gets the short bound once and its retry always gets the full bound.
    """
    first = VISUALLY_EMPTY_TIMEOUT if expected_occupied is False else OCCUPIED_TIMEOUT
    return first, OCCUPIED_TIMEOUT


def best_observation(observations: list[list[str]]) -> list[str]:
    """The attempt with the most item-like text (latest on ties); other attempts stay in raw_events."""
    best = observations[-1]
    for lines in reversed(observations):
        if len(item_lines(lines)) > len(item_lines(best)):
            best = lines
    return list(best)


def classify_without_frame(record: ItemRecord, observations: list[list[str]], expected_occupied: bool | None) -> None:
    """Without a complete frame, only text proves an item and only explicit evidence proves emptiness.

    ``expected_occupied`` is True/False for a settled grid guess and None when no visual guess is
    trustworthy (equipped slots, or grid icons that never stopped changing). An equipped slot's own
    label is the preamble of a real equipped item, so on its own it proves neither an item nor emptiness.
    """
    labels = slot_labels(record.location.slot) if record.location.scope == "equipped" else frozenset()
    heard = [line for lines in observations for line in lines]
    if item_lines(heard, labels=labels):
        record.status = "unparsed"
        record.error = "No complete item trace after hovering; all received raw text is retained."
        if record.truncated:
            record.error = "Item framing exceeded its line limit; untruncated raw observation events are retained."
    elif expected_occupied is True:
        record.status = "timeout"
        record.error = "The slot looked occupied, but no item text was spoken after two hovers."
    elif expected_occupied is False:
        # Settled empty pixels and two bounded silent hovers.
        record.status = "empty"
        record.error = None
    else:
        record.status = "unverified"
        record.error = (
            "Only this slot's own label was spoken; a label without item text does not prove the slot empty."
            if any(line.strip() in labels for line in heard)
            else "No item text or explicit empty-slot announcement; occupancy is unknown."
        )


def apply_title_markers(record: ItemRecord) -> None:
    """Favorite and junk are confirmed only by an explicit marker on the current item title."""
    favorite = observe_favorite(record.raw_tts)
    record.favorite = True if favorite is not None else None
    if favorite is not None:
        record.favorite_evidence.append(favorite)
    junk = observe_junk(record.raw_tts)
    record.junk = True if junk is not None else None
    if junk is not None:
        record.junk_evidence.append(junk)


def restore_title(record: ItemRecord, events: list[RawTtsEvent], snapshot: ItemTraceSnapshot) -> None:
    """Export-only: the shared framer can start at a type line ("梦魇符印") after the real title.

    Only the event immediately before the frame, from this hover, that ends with the frame's first line
    is restored. Equipped-slot labels, "已装备" and neighbouring frames never satisfy that rule.
    """
    if not snapshot.raw_lines:
        return
    first = snapshot.raw_lines[0].strip()
    previous = next((event for event in events if event.sequence == snapshot.raw_start_sequence - 1), None)
    if previous is None or ambient_only([previous.text]):
        return
    title = previous.text.strip()
    if not first or title == first or not title.endswith(first):
        return
    record.raw_tts.insert(0, previous.text)
    record.raw_sequence_start = previous.sequence
    record.raw_reconstruction = {
        "rule": "preceding_line_ends_with_framed_title",
        "restored_lines": [previous.text],
        "parser_input_unchanged": True,
    }
