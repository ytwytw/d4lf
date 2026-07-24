from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Never, cast

from src.locale_data import LocaleGrammar, normalize_locale_text
from src.tools.tts_capture import SCHEMA_VERSION as CAPTURE_SCHEMA_VERSION
from src.tts_framing import TtsFramer, fix_data

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REPORT_SCHEMA_VERSION = 1
ASSET_SCHEMA_VERSION = 1
DEFAULT_MAX_LINES = 500


class ReplayError(ValueError):
    def __init__(self, code: str, message: str, *, line_number: int | None = None) -> None:
        self.code = code
        self.line_number = line_number
        location = f" at line {line_number}" if line_number is not None else ""
        super().__init__(f"{code}{location}: {message}")


def _fail(code: str, message: str, *, line_number: int | None = None, cause: BaseException | None = None) -> Never:
    replay_error = ReplayError(code, message, line_number=line_number)
    if cause is not None:
        raise replay_error from cause
    raise replay_error


@dataclass(frozen=True, slots=True)
class CaptureRecord:
    sequence: int
    raw_text: str

    def as_json(self) -> dict[str, object]:
        return {"sequence": self.sequence, "raw_text": self.raw_text}


@dataclass(frozen=True, slots=True)
class CaptureData:
    source_sha256: str
    locale: str
    game_build: str
    records: tuple[CaptureRecord, ...]


@dataclass(frozen=True, slots=True)
class ReplayAssets:
    grammar: LocaleGrammar
    catalog: ItemTypeCatalog
    grammar_sha256: str
    item_types_sha256: str
    quality_report_sha256: str | None


class ItemTypeCatalog:
    """Minimal, configuration-free item-type resolver for TTS framing."""

    def __init__(self, item_types: Mapping[str, str]) -> None:
        aliases: dict[str, str] = {}
        ambiguous: set[str] = set()
        for canonical, display_name in item_types.items():
            for value in (canonical, canonical.replace("_", " "), display_name):
                normalized = normalize_locale_text(value)
                if not normalized or normalized in ambiguous:
                    continue
                existing = aliases.get(normalized)
                if existing is None:
                    aliases[normalized] = canonical
                elif existing != canonical:
                    aliases.pop(normalized)
                    ambiguous.add(normalized)
        self._aliases = aliases

    def resolve_item_type(self, value: str) -> str | None:
        return self._aliases.get(normalize_locale_text(value))


def _reject_json_constant(value: str) -> None:
    message = f"invalid JSON constant {value}"
    raise ValueError(message)


def _decode_json(data: bytes, *, label: str, line_number: int | None = None) -> object:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        _fail("invalid_utf8", f"{label} is not valid UTF-8", line_number=line_number, cause=error)
    try:
        return json.loads(text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as error:
        _fail("invalid_json", f"{label} is not valid JSON", line_number=line_number, cause=error)


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        _fail("read_failed", f"cannot read {label}: {path}", cause=error)


def _required_string(record: Mapping[str, object], key: str, *, line_number: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        _fail("invalid_field", f"{key} must be a non-empty string", line_number=line_number)
    return value


def load_capture(path: Path) -> CaptureData:
    raw_capture = _read_bytes(path, label="capture file")
    lines = raw_capture.splitlines()
    if not lines:
        _fail("empty_capture", "capture file contains no records")

    records: list[CaptureRecord] = []
    expected_locale: str | None = None
    expected_game_build: str | None = None
    seen_sequences: set[int] = set()
    previous_sequence: int | None = None

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            _fail("blank_line", "capture records must not be blank", line_number=line_number)
        value = _decode_json(line, label="capture record", line_number=line_number)
        if not isinstance(value, dict):
            _fail("invalid_record", "capture record must be a JSON object", line_number=line_number)
        record = cast("dict[str, object]", value)

        schema_version = record.get("schema_version")
        if isinstance(schema_version, bool) or schema_version != CAPTURE_SCHEMA_VERSION:
            _fail("unsupported_schema", f"schema_version must equal {CAPTURE_SCHEMA_VERSION}", line_number=line_number)

        locale = _required_string(record, "locale", line_number=line_number)
        game_build = _required_string(record, "game_build", line_number=line_number)
        if expected_locale is None:
            expected_locale = locale
        elif locale != expected_locale:
            _fail("mixed_locale", f"locale {locale!r} does not match {expected_locale!r}", line_number=line_number)
        if expected_game_build is None:
            expected_game_build = game_build
        elif game_build != expected_game_build:
            _fail(
                "mixed_game_build",
                f"game_build {game_build!r} does not match {expected_game_build!r}",
                line_number=line_number,
            )

        sequence = record.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            _fail("invalid_sequence", "sequence must be a positive integer", line_number=line_number)
        if sequence in seen_sequences:
            _fail("duplicate_sequence", f"sequence {sequence} is repeated", line_number=line_number)
        if previous_sequence is not None and sequence <= previous_sequence:
            _fail(
                "non_monotonic_sequence",
                f"sequence {sequence} must be greater than {previous_sequence}",
                line_number=line_number,
            )

        raw_text = record.get("raw_text")
        if not isinstance(raw_text, str):
            _fail("invalid_raw_text", "raw_text must be a string", line_number=line_number)

        seen_sequences.add(sequence)
        previous_sequence = sequence
        records.append(CaptureRecord(sequence=sequence, raw_text=raw_text))

    if expected_locale is None or expected_game_build is None:
        _fail("empty_capture", "capture file contains no records")
    return CaptureData(
        source_sha256=hashlib.sha256(raw_capture).hexdigest(),
        locale=expected_locale,
        game_build=expected_game_build,
        records=tuple(records),
    )


def _load_json_object(path: Path, *, label: str) -> tuple[dict[str, object], str]:
    raw_data = _read_bytes(path, label=label)
    value = _decode_json(raw_data, label=label)
    if not isinstance(value, dict):
        _fail("invalid_asset", f"{label} must be a JSON object")
    return cast("dict[str, object]", value), hashlib.sha256(raw_data).hexdigest()


def _excluded_item_types(assets_dir: Path) -> tuple[set[str], str | None]:
    quality_report_path = assets_dir / "quality-report.json"
    if not quality_report_path.exists():
        return set(), None

    quality_report, quality_report_sha256 = _load_json_object(quality_report_path, label="quality report")
    scope = quality_report.get("scope")
    if scope is None:
        return set(), quality_report_sha256
    if not isinstance(scope, dict):
        _fail("invalid_asset", "quality report scope must be a JSON object")
    scope_object = cast("dict[str, object]", scope)
    excluded = scope_object.get("excluded_item_types", [])
    if not isinstance(excluded, list):
        _fail("invalid_asset", "quality report excluded_item_types must be an array of non-empty strings")
    excluded_item_types: set[str] = set()
    for value in excluded:
        if not isinstance(value, str) or not value.strip():
            _fail("invalid_asset", "quality report excluded_item_types must be an array of non-empty strings")
        excluded_item_types.add(value)
    return excluded_item_types, quality_report_sha256


def load_assets(assets_dir: Path, *, locale: str) -> ReplayAssets:
    grammar_data, grammar_sha256 = _load_json_object(assets_dir / "grammar.json", label="grammar asset")
    schema_version = grammar_data.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != ASSET_SCHEMA_VERSION:
        _fail("unsupported_asset_schema", f"grammar schema_version must equal {ASSET_SCHEMA_VERSION}")

    item_types_data, item_types_sha256 = _load_json_object(assets_dir / "item_types.json", label="item-types asset")
    if not item_types_data:
        _fail("invalid_asset", "item-types asset must not be empty")
    excluded_item_types, quality_report_sha256 = _excluded_item_types(assets_dir)
    item_types: dict[str, str] = {}
    for canonical, display_name in item_types_data.items():
        if not canonical.strip() or not isinstance(display_name, str):
            _fail("invalid_asset", "item-types entries must map non-empty names to strings")
        if not display_name.strip() and canonical not in excluded_item_types:
            _fail("invalid_asset", f"item-types entry {canonical!r} has an undeclared empty alias")
        item_types[canonical] = display_name

    return ReplayAssets(
        grammar=LocaleGrammar.from_dict(locale, grammar_data),
        catalog=ItemTypeCatalog(item_types),
        grammar_sha256=grammar_sha256,
        item_types_sha256=item_types_sha256,
        quality_report_sha256=quality_report_sha256,
    )


def build_report(
    capture: CaptureData, assets: ReplayAssets, *, max_lines: int = DEFAULT_MAX_LINES
) -> dict[str, object]:
    if isinstance(max_lines, bool) or not isinstance(max_lines, int) or max_lines <= 0:
        _fail("invalid_max_lines", "max_lines must be a positive integer")

    framer = TtsFramer(assets.grammar, assets.catalog, max_lines=max_lines)
    pending_records: list[CaptureRecord] = []
    frames: list[dict[str, object]] = []

    for record in capture.records:
        cleaned_text = fix_data(record.raw_text, grammar=assets.grammar)
        if not cleaned_text:
            continue
        pending_records.append(record)
        if len(pending_records) > max_lines:
            del pending_records[: len(pending_records) - max_lines]

        framed_lines = framer.feed(cleaned_text)
        if framed_lines is None:
            continue
        frame_records = pending_records[-len(framed_lines) :]
        frames.append({
            "start_sequence": frame_records[0].sequence,
            "end_sequence": frame_records[-1].sequence,
            "records": [frame_record.as_json() for frame_record in frame_records],
        })
        pending_records.clear()

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "input": {
            "sha256": capture.source_sha256,
            "schema_version": CAPTURE_SCHEMA_VERSION,
            "locale": capture.locale,
            "game_build": capture.game_build,
            "first_sequence": capture.records[0].sequence,
            "last_sequence": capture.records[-1].sequence,
        },
        "assets": {
            "grammar_sha256": assets.grammar_sha256,
            "item_types_sha256": assets.item_types_sha256,
            "quality_report_sha256": assets.quality_report_sha256,
        },
        "record_count": len(capture.records),
        "frame_count": len(frames),
        "frames": frames,
        "unframed_tail": [record.as_json() for record in pending_records],
    }


def replay_capture(input_path: Path, assets_dir: Path, *, max_lines: int = DEFAULT_MAX_LINES) -> dict[str, object]:
    capture = load_capture(input_path)
    assets = load_assets(assets_dir, locale=capture.locale)
    return build_report(capture, assets, max_lines=max_lines)


def write_report(path: Path, report: Mapping[str, object]) -> None:
    try:
        serialized = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
            "utf-8"
        )
    except (TypeError, ValueError) as error:
        _fail("invalid_report", "report cannot be encoded as JSON", cause=error)

    temporary_path: Path | None = None
    file_descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as output_file:
            file_descriptor = None
            output_file.write(serialized)
            output_file.flush()
            os.fsync(output_file.fileno())
        temporary_path.replace(path)
        temporary_path = None
    except OSError as error:
        _fail("write_failed", f"cannot write report: {path}", cause=error)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay a D4LF TTS capture completely offline.")
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 capture JSONL file")
    parser.add_argument("--assets-dir", required=True, type=Path, help="Locale directory containing grammar.json")
    parser.add_argument("--output", required=True, type=Path, help="Destination UTF-8 JSON report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    try:
        report = replay_capture(arguments.input, arguments.assets_dir)
        write_report(arguments.output, report)
    except ReplayError as error:
        print(f"Replay failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Saved {report['frame_count']} frames from {report['record_count']} records to {arguments.output}.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
