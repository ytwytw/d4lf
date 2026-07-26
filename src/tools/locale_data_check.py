# Structured input errors keep stable machine codes and messages at their call sites.
# ruff: noqa: EM101

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Never, cast, override

from src.tools import d2core_data

SUPPORTED_SCHEMA_VERSION = 1

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_INPUT_ERROR = 2

_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_FLAT_RUNTIME_NAMESPACES = {
    "affixes.json": "affixes",
    "aspects.json": "aspects",
    "charms_affixes.json": "charms_affixes",
    "item_types.json": "item_types",
    "seals_affixes.json": "seals_affixes",
    "sets.json": "sets",
    "tooltips.json": "tooltips",
    "tributes.json": "tributes",
}
_RUNTIME_NAMESPACES = frozenset({*_FLAT_RUNTIME_NAMESPACES.values(), "sigils", "uniques"})


class CheckInputError(Exception):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.issue = _issue(code, message, **details)


class CliUsageError(Exception):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> Never:
        raise CliUsageError(message)


@dataclass(frozen=True)
class Record:
    stable_id: str
    text: str | None
    source_sha256: str | None
    index: int


@dataclass(frozen=True)
class FileHash:
    path: str
    sha256: str


def _issue(code: str, message: str, **details: object) -> dict[str, object]:
    return {"code": code, "message": message, **details}


def _input_error(code: str, message: str, **details: object) -> CheckInputError:
    return CheckInputError(code, message, **details)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path, label: str) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except FileNotFoundError as exc:
        raise _input_error("input_not_found", f"{label} does not exist: {path}", input=label, path=str(path)) from exc
    except OSError as exc:
        raise _input_error(
            "input_read_error", f"Could not read {label}: {path}: {exc}", input=label, path=str(path)
        ) from exc


def _load_json_object(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    try:
        raw_bytes = path.read_bytes()
    except FileNotFoundError as exc:
        raise _input_error("input_not_found", f"{label} does not exist: {path}", input=label, path=str(path)) from exc
    except OSError as exc:
        raise _input_error(
            "input_read_error", f"Could not read {label}: {path}: {exc}", input=label, path=str(path)
        ) from exc

    try:
        value = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _input_error(
            "invalid_json", f"{label} is not valid UTF-8 JSON: {path}: {exc}", input=label, path=str(path)
        ) from exc

    if not isinstance(value, dict):
        raise _input_error(
            "invalid_manifest", f"{label} must contain a JSON object: {path}", input=label, path=str(path)
        )

    return cast("dict[str, object]", value), raw_bytes


def _read_build_version(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise _input_error(
            "input_not_found", f"d4data buildVersion.txt does not exist: {path}", input="build_version", path=str(path)
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise _input_error(
            "input_read_error",
            f"Could not read d4data buildVersion.txt: {path}: {exc}",
            input="build_version",
            path=str(path),
        ) from exc

    if not value or any(character.isspace() for character in value):
        raise _input_error(
            "invalid_build_version",
            f"d4data buildVersion.txt must contain exactly one non-empty value: {path}",
            input="build_version",
            path=str(path),
        )
    return value


def _field(document: dict[str, object], names: tuple[str, ...], label: str) -> object:
    present = [(name, document[name]) for name in names if name in document]
    if not present:
        raise _input_error(
            "missing_field", f"{label} is missing required field '{names[0]}'.", input=label, field=names[0]
        )

    first_name, first_value = present[0]
    if any(value != first_value for _, value in present[1:]):
        raise _input_error(
            "conflicting_fields",
            f"{label} has conflicting values for aliases of '{first_name}'.",
            input=label,
            fields=[name for name, _ in present],
        )
    return first_value


def _optional_field(document: dict[str, object], names: tuple[str, ...], label: str) -> object | None:
    present = [(name, document[name]) for name in names if name in document]
    if not present:
        return None

    first_name, first_value = present[0]
    if any(value != first_value for _, value in present[1:]):
        raise _input_error(
            "conflicting_fields",
            f"{label} has conflicting values for aliases of '{first_name}'.",
            input=label,
            fields=[name for name, _ in present],
        )
    return first_value


def _schema_version(document: dict[str, object], label: str) -> int:
    value = _field(document, ("schema_version", "schemaVersion"), label)
    if type(value) is not int:
        raise _input_error(
            "invalid_field", f"{label}.schema_version must be an integer.", input=label, field="schema_version"
        )
    return value


def _build_version(document: dict[str, object], label: str) -> str:
    value = _field(document, ("build_version", "buildVersion", "d4data_build_version"), label)
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character.isspace() for character in value)
    ):
        raise _input_error(
            "invalid_field",
            f"{label}.build_version must be a non-empty string without whitespace.",
            input=label,
            field="build_version",
        )
    return value


def _valid_sha256(value: object, label: str, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise _input_error(
            "invalid_hash",
            f"{label}.{field} must be a 64-character hexadecimal SHA-256 digest.",
            input=label,
            field=field,
        )
    return value.lower()


def _source_manifest_reference(
    source_lock: dict[str, object], source_lock_path: Path, source_manifest_override: Path | None
) -> tuple[Path, str] | None:
    reference = source_lock.get("source_manifest")
    declared_path: str | None = None
    declared_hash = source_lock.get("source_manifest_sha256")

    if isinstance(reference, str):
        declared_path = reference
    elif isinstance(reference, dict):
        reference_object = cast("dict[str, object]", reference)
        path_value = _field(reference_object, ("path",), "source_lock.source_manifest")
        if not isinstance(path_value, str) or not path_value.strip():
            raise _input_error(
                "invalid_field",
                "source_lock.source_manifest.path must be a non-empty string.",
                input="source_lock",
                field="source_manifest.path",
            )
        declared_path = path_value
        nested_hash = _optional_field(reference_object, ("sha256", "hash"), "source_lock.source_manifest")
        if nested_hash is not None:
            if declared_hash is not None and declared_hash != nested_hash:
                raise _input_error(
                    "conflicting_fields",
                    "source_lock has conflicting source manifest hashes.",
                    input="source_lock",
                    fields=["source_manifest.sha256", "source_manifest_sha256"],
                )
            declared_hash = nested_hash
    elif reference is not None:
        raise _input_error(
            "invalid_field",
            "source_lock.source_manifest must be a path string or object.",
            input="source_lock",
            field="source_manifest",
        )

    if source_manifest_override is None and declared_path is None:
        return None

    manifest_path = source_manifest_override
    if manifest_path is None:
        manifest_path = source_lock_path.parent / cast("str", declared_path)
    if declared_hash is None:
        raise _input_error(
            "missing_field",
            "An external source manifest must have a SHA-256 digest in the source lock.",
            input="source_lock",
            field="source_manifest.sha256",
        )
    return manifest_path, _valid_sha256(declared_hash, "source_lock", "source_manifest.sha256")


def _records(document: dict[str, object], label: str, *, locale: bool) -> list[Record]:
    raw_records = _field(document, ("records",), label)
    if not isinstance(raw_records, list):
        raise _input_error("invalid_field", f"{label}.records must be an array.", input=label, field="records")

    records: list[Record] = []
    for index, raw_record in enumerate(raw_records):
        record_label = f"{label}.records[{index}]"
        if not isinstance(raw_record, dict):
            raise _input_error("invalid_record", f"{record_label} must be an object.", input=label, record_index=index)
        record = cast("dict[str, object]", raw_record)
        stable_id_value = _field(record, ("stable_id", "id"), record_label)
        if not isinstance(stable_id_value, str) or not stable_id_value or stable_id_value != stable_id_value.strip():
            raise _input_error(
                "invalid_record",
                f"{record_label}.stable_id must be a non-empty, trimmed string.",
                input=label,
                record_index=index,
                field="stable_id",
            )

        text_names = ("text", "translation", "value") if locale else ("text", "source_text", "source")
        text_value = _optional_field(record, text_names, record_label)
        if text_value is not None and not isinstance(text_value, str):
            raise _input_error(
                "invalid_record",
                f"{record_label}.{text_names[0]} must be a string when present.",
                input=label,
                record_index=index,
                field=text_names[0],
            )

        hash_value = _optional_field(record, ("source_sha256", "source_hash", "sha256"), record_label)
        source_sha256 = None
        if hash_value is not None:
            source_sha256 = _valid_sha256(hash_value, record_label, "source_sha256")

        records.append(Record(stable_id=stable_id_value, text=text_value, source_sha256=source_sha256, index=index))
    return records


def _file_hashes(document: dict[str, object], label: str) -> list[FileHash]:
    raw_files = document.get("files")
    if raw_files is None:
        return []

    entries: list[tuple[object, object]] = []
    if isinstance(raw_files, dict):
        for path, digest_value in cast("dict[object, object]", raw_files).items():
            resolved_digest = digest_value
            if isinstance(digest_value, dict):
                resolved_digest = _field(
                    cast("dict[str, object]", digest_value), ("sha256", "hash"), f"{label}.files[{path!r}]"
                )
            entries.append((path, resolved_digest))
    elif isinstance(raw_files, list):
        for index, raw_entry in enumerate(raw_files):
            entry_label = f"{label}.files[{index}]"
            if not isinstance(raw_entry, dict):
                raise _input_error(
                    "invalid_field", f"{entry_label} must be an object.", input=label, field=f"files[{index}]"
                )
            entry = cast("dict[str, object]", raw_entry)
            entries.append((_field(entry, ("path",), entry_label), _field(entry, ("sha256", "hash"), entry_label)))
    else:
        raise _input_error("invalid_field", f"{label}.files must be an array or object.", input=label, field="files")

    file_hashes: list[FileHash] = []
    seen: set[str] = set()
    for path_value, hash_value in entries:
        if not isinstance(path_value, str) or not path_value.strip():
            raise _input_error(
                "invalid_field", f"{label} contains a file with an invalid path.", input=label, field="files.path"
            )
        if path_value in seen:
            raise _input_error(
                "duplicate_file", f"{label} contains duplicate file path '{path_value}'.", input=label, path=path_value
            )
        seen.add(path_value)
        file_hashes.append(FileHash(path=path_value, sha256=_valid_sha256(hash_value, label, f"files[{path_value}]")))
    return file_hashes


def _check_schema_versions(
    documents: list[tuple[str, dict[str, object]]], expected_schema_version: int, issues: list[dict[str, object]]
) -> None:
    for label, document in documents:
        actual = _schema_version(document, label)
        if actual != expected_schema_version:
            issues.append(
                _issue(
                    "schema_version_mismatch",
                    f"{label} schema version is {actual}; expected {expected_schema_version}.",
                    input=label,
                    expected=expected_schema_version,
                    actual=actual,
                )
            )


def _check_build_versions(
    documents: list[tuple[str, dict[str, object]]], d4data_build_version: str, issues: list[dict[str, object]]
) -> None:
    expected = _build_version(documents[0][1], documents[0][0])
    if d4data_build_version != expected:
        issues.append(
            _issue(
                "build_mismatch",
                f"d4data buildVersion.txt is '{d4data_build_version}'; source lock expects '{expected}'.",
                input="build_version",
                expected=expected,
                actual=d4data_build_version,
            )
        )

    for label, document in documents[1:]:
        actual = _build_version(document, label)
        if actual != expected:
            issues.append(
                _issue(
                    "build_mismatch",
                    f"{label} build version is '{actual}'; source lock expects '{expected}'.",
                    input=label,
                    expected=expected,
                    actual=actual,
                )
            )


def _check_d2core_release_metadata(
    source_manifest: dict[str, object],
    locale_manifest: dict[str, object],
    expected_build: str,
    issues: list[dict[str, object]],
) -> None:
    sources = source_manifest.get("sources")
    if not isinstance(sources, dict) or "d2core" not in sources:
        return
    d2core_source = sources.get("d2core")
    try:
        _, d2core_build, _, _ = d2core_data.validate_snapshot_manifest(d2core_source)
    except d2core_data.SnapshotValidationError as exc:
        issues.append(
            _issue("invalid_provider_manifest", f"D2Core source metadata is invalid: {exc}", provider="d2core")
        )
        return

    expected_build_id = expected_build.rsplit(".", maxsplit=1)[-1]
    if d2core_build != expected_build_id:
        issues.append(
            _issue(
                "provider_build_mismatch",
                f"D2Core build '{d2core_build}' does not match d4data build '{expected_build}'.",
                provider="d2core",
                expected=expected_build_id,
                actual=d2core_build,
            )
        )

    if locale_manifest.get("runtime_ready") is not True:
        issues.append(
            _issue("runtime_not_ready", "Locale manifest does not declare runtime_ready=true.", input="locale_manifest")
        )

    if locale_manifest.get("source_quality_ok") is not True:
        issues.append(
            _issue(
                "source_quality_failed",
                "Locale manifest does not declare source_quality_ok=true.",
                input="locale_manifest",
            )
        )

    conflicts = locale_manifest.get("translation_conflicts")
    if type(conflicts) is not int or conflicts < 0:
        issues.append(
            _issue(
                "invalid_runtime_metadata",
                "Locale manifest translation_conflicts must be a non-negative integer.",
                input="locale_manifest",
            )
        )
    elif conflicts:
        issues.append(
            _issue(
                "translation_conflict",
                f"Locale manifest has {conflicts} unreviewed provider conflicts.",
                count=conflicts,
            )
        )


_D2CORE_SOURCE_ID_RE = re.compile(r"(?:affix|aspect|uniqueItem|talisman):.+:\d+:x[1-9]\d*")
_D2CORE_DATASETS_BY_NAMESPACE = {
    "affix": {"affix"},
    "affixes": {"affix"},
    "aspects": {"aspect"},
    "charms_affixes": {"affix", "talisman"},
    "seals_affixes": {"affix", "talisman"},
    "sets": {"talisman"},
    "uniques": {"talisman", "uniqueItem"},
}


def _d2core_translation_record_index(
    source_manifest: dict[str, object], issues: list[dict[str, object]]
) -> dict[str, dict[str, str]] | None:
    sources = source_manifest.get("sources")
    if not isinstance(sources, dict) or "d2core" not in sources:
        return None
    source = sources.get("d2core")
    if not isinstance(source, dict):
        return None
    raw_index = source.get("translation_record_index")
    if not isinstance(raw_index, dict) or not raw_index:
        issues.append(
            _issue(
                "invalid_provider_manifest",
                "D2Core source metadata has no derived translation-record index.",
                provider="d2core",
            )
        )
        return None

    index: dict[str, dict[str, str]] = {}
    for source_id, metadata in raw_index.items():
        if (
            not isinstance(source_id, str)
            or _D2CORE_SOURCE_ID_RE.fullmatch(source_id) is None
            or not isinstance(metadata, dict)
        ):
            issues.append(
                _issue(
                    "invalid_provider_manifest",
                    "D2Core source metadata contains an invalid translation-record index entry.",
                    provider="d2core",
                    source_id=source_id,
                )
            )
            return None
        metadata_object = cast("dict[str, object]", metadata)
        source_record_sha256 = metadata_object.get("source_record_sha256")
        translation_sha256 = metadata_object.get("translation_sha256")
        if (
            set(metadata_object) != {"source_record_sha256", "translation_sha256"}
            or not isinstance(source_record_sha256, str)
            or _SHA256_RE.fullmatch(source_record_sha256) is None
            or not isinstance(translation_sha256, str)
            or _SHA256_RE.fullmatch(translation_sha256) is None
        ):
            issues.append(
                _issue(
                    "invalid_provider_manifest",
                    "D2Core source metadata contains an invalid translation-record index entry.",
                    provider="d2core",
                    source_id=source_id,
                )
            )
            return None
        index[source_id] = {
            "source_record_sha256": source_record_sha256.lower(),
            "translation_sha256": translation_sha256.lower(),
        }
    return index


def _check_translation_provenance(
    source_manifest: dict[str, object],
    locale_manifest: dict[str, object],
    issues: list[dict[str, object]],
    d2core_translation_records: dict[str, dict[str, str]] | None,
) -> None:
    sources = source_manifest.get("sources")
    if not isinstance(sources, dict) or "d2core" not in sources:
        return
    raw_records = locale_manifest.get("records")
    if not isinstance(raw_records, list):
        return

    valid_providers = {"d2core", "diablo4_companion", "locale_grammar", "reviewed_override"}
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            continue
        stable_id = raw_record.get("stable_id")
        provenance = raw_record.get("translation_source")
        if not isinstance(provenance, dict):
            issues.append(
                _issue(
                    "translation_provenance_missing",
                    f"Locale record '{stable_id}' has no translation_source metadata.",
                    stable_id=stable_id,
                    record_index=index,
                )
            )
            continue

        provenance_object = cast("dict[str, object]", provenance)
        provider = provenance_object.get("provider")
        source_id = provenance_object.get("source_id")
        translation_hash = provenance_object.get("translation_sha256")
        if provider not in valid_providers:
            issues.append(
                _issue(
                    "translation_provider_invalid",
                    f"Locale record '{stable_id}' has an unknown translation provider.",
                    stable_id=stable_id,
                    provider=provider,
                )
            )
        if not isinstance(source_id, str) or not source_id.strip():
            issues.append(
                _issue(
                    "translation_source_invalid",
                    f"Locale record '{stable_id}' has an invalid translation source ID.",
                    stable_id=stable_id,
                )
            )
        if not isinstance(translation_hash, str) or _SHA256_RE.fullmatch(translation_hash) is None:
            issues.append(
                _issue(
                    "translation_hash_invalid",
                    f"Locale record '{stable_id}' has an invalid translation SHA-256.",
                    stable_id=stable_id,
                )
            )
        text = raw_record.get("text")
        if (
            isinstance(translation_hash, str)
            and _SHA256_RE.fullmatch(translation_hash) is not None
            and isinstance(text, str)
            and translation_hash.lower() != _sha256_text(text)
        ):
            issues.append(
                _issue(
                    "translation_hash_mismatch",
                    f"Locale record '{stable_id}' translation hash does not match its text.",
                    stable_id=stable_id,
                )
            )

        if provider == "d2core":
            source_record_hash = provenance_object.get("source_record_sha256")
            valid_source_id = isinstance(source_id, str) and _D2CORE_SOURCE_ID_RE.fullmatch(source_id) is not None
            valid_source_record_hash = (
                isinstance(source_record_hash, str) and _SHA256_RE.fullmatch(source_record_hash) is not None
            )
            if not valid_source_id:
                issues.append(
                    _issue(
                        "translation_source_invalid",
                        f"Locale record '{stable_id}' has an invalid D2Core source ID.",
                        stable_id=stable_id,
                    )
                )
            if not valid_source_record_hash:
                issues.append(
                    _issue(
                        "translation_source_hash_invalid",
                        f"Locale record '{stable_id}' has no valid D2Core source-record hash.",
                        stable_id=stable_id,
                    )
                )
            if valid_source_id and isinstance(stable_id, str):
                namespace = stable_id.partition(":")[0]
                dataset = source_id.partition(":")[0]
                if dataset not in _D2CORE_DATASETS_BY_NAMESPACE.get(namespace, set()):
                    issues.append(
                        _issue(
                            "translation_source_dataset_mismatch",
                            f"Locale record '{stable_id}' refers to the wrong D2Core dataset.",
                            stable_id=stable_id,
                            source_id=source_id,
                        )
                    )
            if valid_source_id and valid_source_record_hash and d2core_translation_records is not None:
                expected = d2core_translation_records.get(source_id)
                if expected is None:
                    issues.append(
                        _issue(
                            "translation_source_unknown",
                            f"Locale record '{stable_id}' refers to a D2Core record outside the locked index.",
                            stable_id=stable_id,
                            source_id=source_id,
                        )
                    )
                else:
                    if source_record_hash.lower() != expected["source_record_sha256"]:
                        issues.append(
                            _issue(
                                "translation_source_hash_mismatch",
                                f"Locale record '{stable_id}' D2Core source-record hash does not match the locked index.",
                                stable_id=stable_id,
                                source_id=source_id,
                            )
                        )
                    if (
                        isinstance(translation_hash, str)
                        and _SHA256_RE.fullmatch(translation_hash) is not None
                        and translation_hash.lower() != expected["translation_sha256"]
                    ):
                        issues.append(
                            _issue(
                                "translation_source_text_mismatch",
                                f"Locale record '{stable_id}' translation does not match its locked D2Core record.",
                                stable_id=stable_id,
                                source_id=source_id,
                            )
                        )
        elif provider == "diablo4_companion" and "diablo4_companion" not in sources:
            issues.append(
                _issue(
                    "translation_provider_invalid",
                    f"Locale record '{stable_id}' refers to an undeclared Companion source.",
                    stable_id=stable_id,
                )
            )
        elif provider == "reviewed_override" and not isinstance(locale_manifest.get("reviewed_overrides"), dict):
            issues.append(
                _issue(
                    "translation_provider_invalid",
                    f"Locale record '{stable_id}' refers to undeclared reviewed overrides.",
                    stable_id=stable_id,
                )
            )


def _check_declared_files(
    document: dict[str, object], label: str, base_path: Path, issues: list[dict[str, object]]
) -> None:
    for file_hash in _file_hashes(document, label):
        path = Path(file_hash.path)
        if not path.is_absolute():
            path = base_path / path
        try:
            actual = _sha256_file(path, f"{label} file")
        except CheckInputError as exc:
            issues.append(
                _issue(
                    "missing_file",
                    f"{label} declares a file that cannot be read: {path}.",
                    input=label,
                    path=str(path),
                    cause=exc.issue["code"],
                )
            )
            continue
        if actual != file_hash.sha256:
            issues.append(
                _issue(
                    "hash_mismatch",
                    f"SHA-256 mismatch for file declared by {label}: {path}.",
                    input=label,
                    hash_kind="file",
                    path=str(path),
                    expected=file_hash.sha256,
                    actual=actual,
                )
            )


def _normalized_runtime_stable_id(stable_id: str) -> str:
    namespace, separator, remainder = stable_id.partition(":")
    if namespace == "affix":
        namespace = "affixes"
    return f"{namespace}:{remainder}" if separator else namespace


def _runtime_record_texts(
    document: dict[str, object], label: str, base_path: Path, issues: list[dict[str, object]]
) -> dict[str, str]:
    records: dict[str, str] = {}

    def add_record(stable_id: str, text: object, path: Path) -> None:
        if not isinstance(text, str):
            issues.append(
                _issue(
                    "invalid_runtime_record",
                    f"Runtime file '{path}' has a non-string translation for '{stable_id}'.",
                    stable_id=stable_id,
                    path=str(path),
                )
            )
            return
        if stable_id in records:
            issues.append(
                _issue(
                    "duplicate_runtime_record",
                    f"Runtime stable ID '{stable_id}' is declared more than once.",
                    stable_id=stable_id,
                    path=str(path),
                )
            )
            return
        records[stable_id] = text

    for file_hash in _file_hashes(document, label):
        declared_path = Path(file_hash.path)
        filename = declared_path.name
        if filename not in _FLAT_RUNTIME_NAMESPACES and filename not in {"sigils.json", "uniques.json"}:
            continue
        path = declared_path if declared_path.is_absolute() else base_path / declared_path
        try:
            payload, _ = _load_json_object(path, f"{label} runtime file")
        except CheckInputError as exc:
            issues.append(
                _issue(
                    "invalid_runtime_file",
                    f"Declared runtime file cannot be validated: {path}.",
                    path=str(path),
                    cause=exc.issue["code"],
                )
            )
            continue

        if namespace := _FLAT_RUNTIME_NAMESPACES.get(filename):
            for canonical, text in payload.items():
                add_record(f"{namespace}:{canonical}", text, path)
            continue

        if filename == "uniques.json":
            for canonical, metadata in payload.items():
                display_name = metadata.get("display_name") if isinstance(metadata, dict) else None
                add_record(f"uniques:{canonical}", display_name, path)
            continue

        for section, section_records in payload.items():
            if section == "rarities":
                continue
            if not isinstance(section_records, dict):
                issues.append(
                    _issue(
                        "invalid_runtime_record",
                        f"Runtime sigil section '{section}' in '{path}' is not an object.",
                        stable_id=f"sigils:{section}",
                        path=str(path),
                    )
                )
                continue
            for canonical, text in section_records.items():
                add_record(f"sigils:{section}:{canonical}", text, path)
    return records


def _check_runtime_records(
    source_records: list[Record],
    locale_records: list[Record],
    runtime_records: dict[str, str],
    issues: list[dict[str, object]],
) -> None:
    source_ids = {
        _normalized_runtime_stable_id(record.stable_id)
        for record in source_records
        if record.stable_id.partition(":")[0] in _RUNTIME_NAMESPACES | {"affix"}
    }
    locale_by_id = {
        _normalized_runtime_stable_id(record.stable_id): record
        for record in locale_records
        if record.stable_id.partition(":")[0] in _RUNTIME_NAMESPACES | {"affix"}
    }

    issues.extend(
        (
            _issue(
                "runtime_record_missing",
                f"Runtime locale files are missing source stable ID '{stable_id}'.",
                stable_id=stable_id,
            )
        )
        for stable_id in sorted(source_ids - runtime_records.keys())
    )

    for stable_id, record in sorted(locale_by_id.items()):
        runtime_text = runtime_records.get(stable_id)
        if runtime_text is None:
            continue
        if runtime_text != record.text:
            issues.append(
                _issue(
                    "runtime_translation_mismatch",
                    f"Runtime text does not match the locale manifest for stable ID '{stable_id}'.",
                    stable_id=stable_id,
                    expected=record.text,
                    actual=runtime_text,
                )
            )

    for stable_id, runtime_text in sorted(runtime_records.items()):
        if runtime_text.strip() and stable_id not in locale_by_id:
            issues.append(
                _issue(
                    "runtime_translation_untracked",
                    f"Runtime text for stable ID '{stable_id}' is not declared by the locale manifest.",
                    stable_id=stable_id,
                )
            )


def _first_by_stable_id(records: list[Record]) -> dict[str, Record]:
    result: dict[str, Record] = {}
    for record in records:
        result.setdefault(record.stable_id, record)
    return result


def _is_ascii_placeholder(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.isascii() and any("a" <= character.lower() <= "z" for character in stripped)


def _check_records(source_records: list[Record], locale_records: list[Record], issues: list[dict[str, object]]) -> None:
    source_counts = Counter(record.stable_id for record in source_records)
    locale_counts = Counter(record.stable_id for record in locale_records)

    for manifest, counts in (("source", source_counts), ("locale", locale_counts)):
        for stable_id, count in sorted(counts.items()):
            if count > 1:
                issues.append(
                    _issue(
                        "duplicate_record",
                        f"{manifest} manifest contains stable ID '{stable_id}' {count} times.",
                        manifest=manifest,
                        stable_id=stable_id,
                        count=count,
                    )
                )

    source_by_id = _first_by_stable_id(source_records)
    locale_by_id = _first_by_stable_id(locale_records)

    issues.extend(
        _issue("missing_record", f"Locale manifest is missing source stable ID '{stable_id}'.", stable_id=stable_id)
        for stable_id in sorted(source_by_id.keys() - locale_by_id.keys())
    )
    issues.extend(
        _issue("new_record", f"Locale manifest has unknown stable ID '{stable_id}'.", stable_id=stable_id)
        for stable_id in sorted(locale_by_id.keys() - source_by_id.keys())
    )

    for record in source_records:
        if record.source_sha256 is None:
            issues.append(
                _issue(
                    "hash_missing",
                    f"Source record '{record.stable_id}' has no source SHA-256 digest.",
                    manifest="source",
                    stable_id=record.stable_id,
                    record_index=record.index,
                )
            )
        if record.text is not None and record.source_sha256 is not None:
            actual = _sha256_text(record.text)
            if actual != record.source_sha256:
                issues.append(
                    _issue(
                        "hash_mismatch",
                        f"Source text hash does not match for stable ID '{record.stable_id}'.",
                        manifest="source",
                        hash_kind="record_text",
                        stable_id=record.stable_id,
                        expected=record.source_sha256,
                        actual=actual,
                    )
                )

    checked_locale_ids: set[str] = set()
    for record in locale_records:
        if record.source_sha256 is None:
            issues.append(
                _issue(
                    "hash_missing",
                    f"Locale record '{record.stable_id}' has no source SHA-256 digest.",
                    manifest="locale",
                    stable_id=record.stable_id,
                    record_index=record.index,
                )
            )
        if record.stable_id in checked_locale_ids:
            continue
        checked_locale_ids.add(record.stable_id)
        if record.text is None or not record.text.strip():
            issues.append(
                _issue(
                    "missing_translation",
                    f"Locale record '{record.stable_id}' has no translated text.",
                    stable_id=record.stable_id,
                )
            )
        elif _is_ascii_placeholder(record.text):
            issues.append(
                _issue(
                    "ascii_placeholder",
                    f"Locale record '{record.stable_id}' still contains ASCII-only text.",
                    stable_id=record.stable_id,
                )
            )

    for stable_id in sorted(source_by_id.keys() & locale_by_id.keys()):
        source_record = source_by_id[stable_id]
        locale_record = locale_by_id[stable_id]
        if (
            source_record.source_sha256 is not None
            and locale_record.source_sha256 is not None
            and source_record.source_sha256 != locale_record.source_sha256
        ):
            issues.append(
                _issue(
                    "hash_mismatch",
                    f"Locale record '{stable_id}' was generated from a different source record hash.",
                    manifest="locale",
                    hash_kind="source_record",
                    stable_id=stable_id,
                    expected=source_record.source_sha256,
                    actual=locale_record.source_sha256,
                )
            )


def _report(
    *,
    exit_code: int,
    expected_schema_version: int,
    inputs: dict[str, str | None],
    issues: list[dict[str, object]],
    source_records: int = 0,
    locale_records: int = 0,
) -> dict[str, object]:
    issue_counts = Counter(cast("str", issue["code"]) for issue in issues)
    status = {EXIT_OK: "ok", EXIT_CHECK_FAILED: "failed", EXIT_INPUT_ERROR: "input_error"}[exit_code]
    return {
        "ok": exit_code == EXIT_OK,
        "status": status,
        "exit_code": exit_code,
        "schema_version": expected_schema_version,
        "inputs": inputs,
        "summary": {
            "source_records": source_records,
            "locale_records": locale_records,
            "issues": len(issues),
            "issue_counts": dict(sorted(issue_counts.items())),
        },
        "issues": issues,
    }


def check_locale_data(
    *,
    source_lock: Path,
    build_version: Path,
    locale_manifest: Path,
    source_manifest: Path | None = None,
    expected_schema_version: int = SUPPORTED_SCHEMA_VERSION,
) -> dict[str, object]:
    inputs = {
        "source_lock": str(source_lock),
        "source_manifest": str(source_manifest) if source_manifest is not None else None,
        "build_version": str(build_version),
        "locale_manifest": str(locale_manifest),
    }
    if expected_schema_version <= 0:
        return _report(
            exit_code=EXIT_INPUT_ERROR,
            expected_schema_version=expected_schema_version,
            inputs=inputs,
            issues=[
                _issue(
                    "invalid_schema_version",
                    "Expected schema version must be a positive integer.",
                    field="expected_schema_version",
                )
            ],
        )

    try:
        source_lock_document, _ = _load_json_object(source_lock, "source_lock")
        reference = _source_manifest_reference(source_lock_document, source_lock, source_manifest)
        source_manifest_path: Path | None = None
        expected_source_manifest_hash: str | None = None
        source_manifest_document = source_lock_document
        source_manifest_bytes: bytes | None = None
        if reference is not None:
            source_manifest_path, expected_source_manifest_hash = reference
            source_manifest_document, source_manifest_bytes = _load_json_object(source_manifest_path, "source_manifest")
            inputs["source_manifest"] = str(source_manifest_path)

        locale_manifest_document, _ = _load_json_object(locale_manifest, "locale_manifest")
        d4data_build_version = _read_build_version(build_version)

        documents = [("source_lock", source_lock_document)]
        if source_manifest_document is not source_lock_document:
            documents.append(("source_manifest", source_manifest_document))
        documents.append(("locale_manifest", locale_manifest_document))

        issues: list[dict[str, object]] = []
        _check_schema_versions(documents, expected_schema_version, issues)
        _check_build_versions(documents, d4data_build_version, issues)
        _check_d2core_release_metadata(
            source_manifest_document,
            locale_manifest_document,
            _build_version(source_manifest_document, "source_manifest"),
            issues,
        )

        if source_manifest_bytes is not None:
            if source_manifest_path is None or expected_source_manifest_hash is None:
                raise _input_error(
                    "invalid_manifest", "Source manifest reference metadata is incomplete.", input="source_manifest"
                )
            actual_source_manifest_hash = _sha256_bytes(source_manifest_bytes)
            if actual_source_manifest_hash != expected_source_manifest_hash:
                issues.append(
                    _issue(
                        "hash_mismatch",
                        "Source manifest SHA-256 does not match the source lock.",
                        input="source_manifest",
                        hash_kind="manifest",
                        path=str(source_manifest_path),
                        expected=expected_source_manifest_hash,
                        actual=actual_source_manifest_hash,
                    )
                )

            locale_source_hash = _optional_field(
                locale_manifest_document, ("source_manifest_sha256", "source_manifest_hash"), "locale_manifest"
            )
            if locale_source_hash is None:
                issues.append(
                    _issue(
                        "hash_missing",
                        "Locale manifest does not declare the source manifest SHA-256.",
                        input="locale_manifest",
                        hash_kind="source_manifest",
                    )
                )
            else:
                expected_locale_source_hash = _valid_sha256(
                    locale_source_hash, "locale_manifest", "source_manifest_sha256"
                )
                if expected_locale_source_hash != actual_source_manifest_hash:
                    issues.append(
                        _issue(
                            "hash_mismatch",
                            "Locale manifest refers to a different source manifest SHA-256.",
                            input="locale_manifest",
                            hash_kind="source_manifest",
                            expected=actual_source_manifest_hash,
                            actual=expected_locale_source_hash,
                        )
                    )

        _check_declared_files(source_lock_document, "source_lock", build_version.parent, issues)
        if source_manifest_path is not None:
            _check_declared_files(source_manifest_document, "source_manifest", source_manifest_path.parent, issues)
        _check_declared_files(locale_manifest_document, "locale_manifest", locale_manifest.parent, issues)

        source_records = _records(source_manifest_document, "source_manifest", locale=False)
        locale_records = _records(locale_manifest_document, "locale_manifest", locale=True)
        if not source_records:
            issues.append(_issue("missing_record", "Source manifest contains no records.", manifest="source"))
        _check_records(source_records, locale_records, issues)
        runtime_records = _runtime_record_texts(
            locale_manifest_document, "locale_manifest", locale_manifest.parent, issues
        )
        _check_runtime_records(source_records, locale_records, runtime_records, issues)
        d2core_translation_records = _d2core_translation_record_index(source_manifest_document, issues)
        _check_translation_provenance(
            source_manifest_document, locale_manifest_document, issues, d2core_translation_records
        )

        exit_code = EXIT_OK if not issues else EXIT_CHECK_FAILED
        return _report(
            exit_code=exit_code,
            expected_schema_version=expected_schema_version,
            inputs=inputs,
            issues=issues,
            source_records=len(source_records),
            locale_records=len(locale_records),
        )
    except CheckInputError as exc:
        return _report(
            exit_code=EXIT_INPUT_ERROR,
            expected_schema_version=expected_schema_version,
            inputs=inputs,
            issues=[exc.issue],
        )


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description="Validate generated locale data against a locked d4data source.")
    parser.add_argument("--source-lock", required=True, type=Path, help="Path to the source lock JSON.")
    parser.add_argument(
        "--source-manifest",
        type=Path,
        help="Optional source manifest path override; otherwise use the source lock reference or embedded records.",
    )
    parser.add_argument(
        "--build-version", "--d4data-build-version", required=True, type=Path, help="Path to d4data/buildVersion.txt."
    )
    parser.add_argument(
        "--locale-manifest", required=True, type=Path, help="Path to the generated locale manifest JSON."
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        default=SUPPORTED_SCHEMA_VERSION,
        help=f"Expected manifest schema version (default: {SUPPORTED_SCHEMA_VERSION}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except CliUsageError as exc:
        report = _report(
            exit_code=EXIT_INPUT_ERROR,
            expected_schema_version=SUPPORTED_SCHEMA_VERSION,
            inputs={},
            issues=[_issue("invalid_arguments", str(exc))],
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return EXIT_INPUT_ERROR

    report = check_locale_data(
        source_lock=args.source_lock,
        source_manifest=args.source_manifest,
        build_version=args.build_version,
        locale_manifest=args.locale_manifest,
        expected_schema_version=args.schema_version,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return cast("int", report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
