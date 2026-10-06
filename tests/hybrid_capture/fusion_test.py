from typing import TYPE_CHECKING, cast

from src.hybrid_capture import Candidate, CaptureContext, Identity, compare_identity, fuse_evidence

if TYPE_CHECKING:
    from src.type_aliases import JsonObject

IDENTITY = Identity("示例指环", "先祖神话暗金戒指", 900)
CONTEXT = CaptureContext("hover-17", "stash/1/r1c1", 200, 218)


def _identity_status(result: JsonObject) -> str:
    identity = result["identity"]
    assert isinstance(identity, dict)
    status = identity["status"]
    assert isinstance(status, str)
    return status


def _field(result: JsonObject, name: str) -> JsonObject:
    fields = result["fields"]
    assert isinstance(fields, dict)
    field = fields[name]
    assert isinstance(field, dict)
    return cast("JsonObject", field)


def test_same_name_different_type_and_power_is_rejected():
    visual = Identity("示例指环", "暗金神符", 850)
    result = fuse_evidence(
        tts_identity=IDENTITY,
        visual_identity=visual,
        tts_context=CONTEXT,
        visual_context=CONTEXT,
        candidates=[Candidate("socket_total", 2, "template", "image-sha/roi")],
    )
    assert _identity_status(result) == "mismatch"
    assert result["visual_fusion"] == "withheld"
    assert _field(result, "socket_total")["value"] is None


def test_matching_headers_do_not_replace_missing_capture_correlation():
    result = fuse_evidence(
        tts_identity=IDENTITY,
        visual_identity=IDENTITY,
        candidates=[Candidate("visible_empty_sockets", 1, "template", "image-sha/roi")],
    )
    assert _identity_status(result) == "content_consistent"
    assert result["capture_association"] == "unverified"
    assert _field(result, "visible_empty_sockets")["value"] is None


def test_tts_value_survives_ocr_conflict_with_both_sources_retained():
    candidates = [
        Candidate("sell_value", 35492, "raw_tts", "events/213"),
        Candidate("sell_value", 3592, "ocr", "image-sha/line-12"),
    ]
    result = fuse_evidence(
        tts_identity=IDENTITY,
        visual_identity=IDENTITY,
        candidates=candidates,
        tts_context=CONTEXT,
        visual_context=CONTEXT,
    )
    field = _field(result, "sell_value")
    assert field["value"] == 35492
    assert field["status"] == "conflict"
    evidence = field["evidence"]
    assert isinstance(evidence, list)
    assert len(evidence) == 2


def test_visual_supplement_never_promotes_manual_annotations_or_unknown_to_false():
    result = fuse_evidence(
        tts_identity=IDENTITY,
        visual_identity=IDENTITY,
        tts_context=CONTEXT,
        visual_context=CONTEXT,
        candidates=[
            Candidate("visible_empty_sockets", 1, "template", "image-sha/roi"),
            Candidate("socket_total", 2, "manual_annotation", "review-1"),
            Candidate("seasonal", None, "raw_tts", "events/200-218"),
        ],
    )
    assert _field(result, "visible_empty_sockets")["value"] == 1
    assert _field(result, "socket_total")["value"] is None
    assert _field(result, "seasonal")["value"] is None


def test_same_item_at_a_different_hover_is_not_correlated():
    result = fuse_evidence(
        tts_identity=IDENTITY,
        visual_identity=IDENTITY,
        tts_context=CONTEXT,
        visual_context=CaptureContext("hover-18", CONTEXT.location, 219, 237),
        candidates=[],
    )
    assert result["visual_fusion"] == "withheld"


def test_missing_identity_and_ocr_substitutions_are_not_guessed():
    assert compare_identity(IDENTITY, Identity("示例指环", "先祖神话暗金戒指", None))["status"] == "unknown"
    assert compare_identity(IDENTITY, Identity("示例指坏", "先祖神话暗金戒指", 900))["status"] == "mismatch"
    assert compare_identity(IDENTITY, Identity("示例 指环", "先祖 神话暗金戒指", 900))["status"] == "content_consistent"


def test_whitespace_only_identity_cannot_open_the_gate():
    blank = Identity(" \t", "\u3000", 900)
    result = fuse_evidence(
        tts_identity=blank, visual_identity=blank, candidates=[], tts_context=CONTEXT, visual_context=CONTEXT
    )
    assert _identity_status(result) == "unknown"
    assert result["visual_fusion"] == "withheld"
