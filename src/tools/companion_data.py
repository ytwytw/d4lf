from __future__ import annotations

# Rich validation paths are more useful here than hoisting every exception message.
# ruff: noqa: EM101, EM102
import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET  # noqa: S405 - parses a trusted, local repository file
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LOCALES = ("enUS", "zhCN")
MANIFEST_FILENAME = "companion-manifest.json"
QUALITY_REPORT_FILENAME = "companion-quality-report.json"
SCHEMA_VERSION = 1

JsonObject = dict[str, object]
RecordKey = tuple[str, str, int]


class CompanionDataError(RuntimeError):
    pass


class SchemaValidationError(CompanionDataError):
    pass


class _DuplicateJsonKeyError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    kind: str
    filename_stem: str
    alias_field: str
    scalar_fields: Mapping[str, type]
    list_fields: Mapping[str, type]


@dataclass(frozen=True)
class SourceRecord:
    kind: str
    locale: str
    source_file: str
    source_index: int
    sno_ids: tuple[str, ...]
    name_ids: tuple[str, ...]
    locale_alias: str

    @property
    def key(self) -> RecordKey:
        return (self.kind, self.locale, self.source_index)


@dataclass(frozen=True)
class CanonicalEntry:
    canonical_id: str
    kind: str
    sno_aliases: tuple[str, ...]
    name_aliases: tuple[str, ...]
    locale_aliases: Mapping[str, tuple[str, ...]]
    record_keys: tuple[RecordKey, ...]

    def as_json(self) -> JsonObject:
        return {
            "canonical_id": self.canonical_id,
            "kind": self.kind,
            "identity_aliases": {"id_name": list(self.name_aliases), "id_sno": list(self.sno_aliases)},
            "locale_aliases": {locale: list(self.locale_aliases[locale]) for locale in LOCALES},
        }


@dataclass(frozen=True)
class GeneratedPaths:
    manifest: Path
    quality_report: Path


_COMMON_SCALARS: dict[str, type] = {"IdSno": str, "IdName": str}
_COMMON_LISTS: dict[str, type] = {
    "IdSnoList": str,
    "IdNameList": str,
    "AllowedForPlayerClass": int,
    "AllowedItemLabels": int,
}

DATASET_SPECS = (
    DatasetSpec(
        kind="affix",
        filename_stem="Affixes",
        alias_field="DescriptionClean",
        scalar_fields={
            **_COMMON_SCALARS,
            "AffixType": int,
            "Category": int,
            "Flags": int,
            "IsTemperingAvailable": bool,
            "MagicType": int,
            "ClassRestriction": str,
            "Description": str,
            "DescriptionClean": str,
        },
        list_fields={**_COMMON_LISTS, "AffixAttributes": dict},
    ),
    DatasetSpec(
        kind="aspect",
        filename_stem="Aspects",
        alias_field="Name",
        scalar_fields={
            **_COMMON_SCALARS,
            "Name": str,
            "Description": str,
            "DescriptionClean": str,
            "Localisation": str,
            "IsSeasonal": bool,
            "IsCodex": bool,
            "Dungeon": str,
            "Category": str,
            "MagicType": int,
        },
        list_fields=_COMMON_LISTS,
    ),
    DatasetSpec(
        kind="unique",
        filename_stem="Uniques",
        alias_field="Name",
        scalar_fields={
            **_COMMON_SCALARS,
            "IdNameItem": str,
            "IdNameItemActor": str,
            "Name": str,
            "Description": str,
            "DescriptionClean": str,
            "Localisation": str,
            "MagicType": int,
        },
        list_fields={**_COMMON_LISTS, "IdNameItemList": str},
    ),
)

_SPEC_BY_KIND = {spec.kind: spec for spec in DATASET_SPECS}
_KIND_ORDER = {spec.kind: index for index, spec in enumerate(DATASET_SPECS)}
_GAME_BUILD_PATTERN = re.compile(r"(?<!\d)(\d+\.\d+\.\d+\.\d+)(?!\d)")
_SNO_PATTERN = re.compile(r"(?:0|[1-9]\d*)")


def _json_object(pairs: list[tuple[str, object]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _copy_json_object(value: Mapping[str, object]) -> JsonObject:
    return dict(value)


def _reject_json_constant(value: str):
    raise ValueError(f"non-standard JSON value {value}")


def _load_json(path: Path, source_name: str):
    try:
        with path.open(encoding="utf-8") as source_file:
            return json.load(source_file, object_pairs_hook=_json_object, parse_constant=_reject_json_constant)
    except FileNotFoundError as exc:
        raise CompanionDataError(f"missing source file: {source_name}") from exc
    except UnicodeDecodeError as exc:
        raise CompanionDataError(f"{source_name} is not valid UTF-8 at byte {exc.start}") from exc
    except json.JSONDecodeError as exc:
        raise CompanionDataError(
            f"{source_name} contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except (_DuplicateJsonKeyError, ValueError) as exc:
        raise CompanionDataError(f"{source_name} contains invalid JSON: {exc}") from exc


def _matches_type(value: object, expected_type: type) -> bool:
    if expected_type is int:
        return type(value) is int
    if expected_type is bool:
        return type(value) is bool
    return isinstance(value, expected_type)


def _validate_list(record: Mapping[str, object], field: str, element_type: type, location: str) -> list[object]:
    if field not in record:
        raise SchemaValidationError(f"{location}: missing required field {field}")
    value = record[field]
    if not isinstance(value, list):
        raise SchemaValidationError(f"{location}.{field}: expected array, got {type(value).__name__}")
    items = cast("list[object]", value)
    for index, element in enumerate(items):
        if not _matches_type(element, element_type):
            raise SchemaValidationError(
                f"{location}.{field}[{index}]: expected {element_type.__name__}, got {type(element).__name__}"
            )
    return items


def _validated_strings(values: Sequence[object], location: str) -> tuple[str, ...]:
    strings: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise SchemaValidationError(f"{location}[{index}]: expected str, got {type(value).__name__}")
        strings.append(value)
    return tuple(strings)


def _validate_affix_attributes(attributes: Sequence[object], location: str) -> None:
    expected_fields = {
        "LocalisationId": str,
        "LocalisationParameter": int,
        "LocalisationAttributeFormulaValue": str,
        "Localisation": str,
    }
    for index, attribute in enumerate(attributes):
        attribute_location = f"{location}.AffixAttributes[{index}]"
        if not isinstance(attribute, dict):
            raise SchemaValidationError(f"{attribute_location}: expected object")
        attribute_value = cast("Mapping[str, object]", attribute)
        for field, expected_type in expected_fields.items():
            if field not in attribute_value:
                raise SchemaValidationError(f"{attribute_location}: missing required field {field}")
            value = attribute_value[field]
            if not _matches_type(value, expected_type):
                raise SchemaValidationError(
                    f"{attribute_location}.{field}: expected {expected_type.__name__}, got {type(value).__name__}"
                )


def _validate_record(record: object, spec: DatasetSpec, locale: str, source_file: str, index: int) -> SourceRecord:
    location = f"{source_file}[{index}]"
    if not isinstance(record, dict):
        raise SchemaValidationError(f"{location}: expected object, got {type(record).__name__}")
    record_value = cast("Mapping[str, object]", record)

    for field, expected_type in spec.scalar_fields.items():
        if field not in record_value:
            raise SchemaValidationError(f"{location}: missing required field {field}")
        value = record_value[field]
        if not _matches_type(value, expected_type):
            raise SchemaValidationError(
                f"{location}.{field}: expected {expected_type.__name__}, got {type(value).__name__}"
            )

    validated_lists = {
        field: _validate_list(record_value, field, element_type, location)
        for field, element_type in spec.list_fields.items()
    }
    sno_ids = _validated_strings(validated_lists["IdSnoList"], f"{location}.IdSnoList")
    name_ids = _validated_strings(validated_lists["IdNameList"], f"{location}.IdNameList")
    if not sno_ids:
        raise SchemaValidationError(f"{location}.IdSnoList: expected at least one identifier")
    if len(sno_ids) != len(name_ids):
        raise SchemaValidationError(
            f"{location}: IdSnoList and IdNameList must have equal lengths, got {len(sno_ids)} and {len(name_ids)}"
        )
    for sno_index, sno_id in enumerate(sno_ids):
        if _SNO_PATTERN.fullmatch(sno_id) is None:
            raise SchemaValidationError(f"{location}.IdSnoList[{sno_index}]: expected a canonical decimal string")
    for name_index, name_id in enumerate(name_ids):
        if not name_id.strip():
            raise SchemaValidationError(f"{location}.IdNameList[{name_index}]: expected a non-empty string")

    if record_value["IdSno"] != ";".join(sno_ids):
        raise SchemaValidationError(f"{location}.IdSno: does not match IdSnoList")
    if record_value["IdName"] != ";".join(name_ids):
        raise SchemaValidationError(f"{location}.IdName: does not match IdNameList")
    if spec.kind == "affix":
        _validate_affix_attributes(validated_lists["AffixAttributes"], location)

    locale_alias = record_value[spec.alias_field]
    if not isinstance(locale_alias, str):
        raise SchemaValidationError(f"{location}.{spec.alias_field}: expected str, got {type(locale_alias).__name__}")

    return SourceRecord(
        kind=spec.kind,
        locale=locale,
        source_file=source_file,
        source_index=index,
        sno_ids=sno_ids,
        name_ids=name_ids,
        locale_alias=locale_alias,
    )


def load_locale_records(companion_repo: Path, spec: DatasetSpec, locale: str) -> list[SourceRecord]:
    source_file = f"D4Companion/Data/{spec.filename_stem}.{locale}.json"
    payload = _load_json(companion_repo / Path(source_file), source_file)
    if not isinstance(payload, list):
        raise SchemaValidationError(f"{source_file}: expected a top-level array, got {type(payload).__name__}")
    return [_validate_record(record, spec, locale, source_file, index) for index, record in enumerate(payload)]


def load_companion_records(companion_repo: Path) -> list[SourceRecord]:
    if not companion_repo.is_dir():
        raise CompanionDataError("Diablo4Companion source directory does not exist")
    return [
        record
        for spec in DATASET_SPECS
        for locale in LOCALES
        for record in load_locale_records(companion_repo, spec, locale)
    ]


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        parent = self._parent[item]
        if parent != item:
            self._parent[item] = self.find(parent)
        return self._parent[item]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        smaller, larger = sorted((left_root, right_root))
        self._parent[larger] = smaller


def _sno_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value)


def _entry_sort_key(entry: CanonicalEntry) -> tuple[int, int, str]:
    sno = entry.canonical_id.split(":", maxsplit=1)[1]
    return (_KIND_ORDER[entry.kind], int(sno), entry.canonical_id)


def join_records(records: Sequence[SourceRecord]) -> tuple[list[CanonicalEntry], dict[RecordKey, str]]:
    entries: list[CanonicalEntry] = []
    canonical_by_record: dict[RecordKey, str] = {}

    for spec in DATASET_SPECS:
        kind_records = [record for record in records if record.kind == spec.kind]
        disjoint_set = _DisjointSet(len(kind_records))
        first_record_by_alias: dict[tuple[str, str], int] = {}
        for index, record in enumerate(kind_records):
            for alias_type, aliases in (("sno", record.sno_ids), ("name", record.name_ids)):
                for alias in set(aliases):
                    alias_key = (alias_type, alias)
                    if alias_key in first_record_by_alias:
                        disjoint_set.union(index, first_record_by_alias[alias_key])
                    else:
                        first_record_by_alias[alias_key] = index

        components: dict[int, list[SourceRecord]] = defaultdict(list)
        for index, record in enumerate(kind_records):
            components[disjoint_set.find(index)].append(record)

        for component_records in components.values():
            sno_aliases = tuple(
                sorted({alias for record in component_records for alias in record.sno_ids}, key=_sno_sort_key)
            )
            name_aliases = tuple(sorted({alias for record in component_records for alias in record.name_ids}))
            canonical_id = f"{spec.kind}:{sno_aliases[0]}"
            locale_aliases = {
                locale: tuple(
                    sorted({
                        record.locale_alias
                        for record in component_records
                        if record.locale == locale and record.locale_alias.strip()
                    })
                )
                for locale in LOCALES
            }
            record_keys = tuple(sorted(record.key for record in component_records))
            entry = CanonicalEntry(
                canonical_id=canonical_id,
                kind=spec.kind,
                sno_aliases=sno_aliases,
                name_aliases=name_aliases,
                locale_aliases=locale_aliases,
                record_keys=record_keys,
            )
            entries.append(entry)
            for record_key in record_keys:
                canonical_by_record[record_key] = canonical_id

    entries.sort(key=_entry_sort_key)
    return entries, canonical_by_record


def _normalise_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _identity_duplicates(
    records: Sequence[SourceRecord], canonical_by_record: Mapping[RecordKey, str]
) -> list[JsonObject]:
    occurrences: dict[tuple[str, str, str, str], list[RecordKey]] = defaultdict(list)
    for record in records:
        for source_field, aliases in (("IdSnoList", record.sno_ids), ("IdNameList", record.name_ids)):
            for alias in aliases:
                occurrences[record.kind, record.locale, source_field, alias].append(record.key)

    duplicates = []
    for (kind, locale, source_field, alias), record_keys in occurrences.items():
        if len(record_keys) < 2:
            continue
        duplicates.append({
            "alias": alias,
            "canonical_ids": sorted({canonical_by_record[record_key] for record_key in record_keys}),
            "kind": kind,
            "locale": locale,
            "occurrence_count": len(record_keys),
            "record_indices": sorted({record_key[2] for record_key in record_keys}),
            "source_field": source_field,
        })
    duplicates.sort(
        key=lambda duplicate: (
            _KIND_ORDER[duplicate["kind"]],
            LOCALES.index(duplicate["locale"]),
            duplicate["source_field"],
            duplicate["alias"],
        )
    )
    return [_copy_json_object(duplicate) for duplicate in duplicates]


def _locale_alias_duplicates(entries: Sequence[CanonicalEntry]) -> list[JsonObject]:
    aliases: dict[tuple[str, str, str], dict[str, set[str]]] = defaultdict(
        lambda: {"aliases": set(), "canonical_ids": set()}
    )
    for entry in entries:
        for locale, locale_aliases in entry.locale_aliases.items():
            for alias in locale_aliases:
                alias_group = aliases[entry.kind, locale, _normalise_alias(alias)]
                alias_group["aliases"].add(alias)
                alias_group["canonical_ids"].add(entry.canonical_id)

    duplicates = [
        {
            "aliases": sorted(alias_group["aliases"]),
            "canonical_ids": sorted(alias_group["canonical_ids"]),
            "kind": kind,
            "locale": locale,
            "normalised_alias": normalised_alias,
        }
        for (kind, locale, normalised_alias), alias_group in aliases.items()
        if len(alias_group["canonical_ids"]) > 1
    ]
    duplicates.sort(
        key=lambda duplicate: (
            _KIND_ORDER[duplicate["kind"]],
            LOCALES.index(duplicate["locale"]),
            duplicate["normalised_alias"],
        )
    )
    return [_copy_json_object(duplicate) for duplicate in duplicates]


def _missing_findings(entries: Sequence[CanonicalEntry]) -> tuple[list[JsonObject], list[JsonObject]]:
    missing_records = []
    missing_aliases = []
    for entry in entries:
        record_locales = {record_key[1] for record_key in entry.record_keys}
        for locale in LOCALES:
            if locale not in record_locales:
                missing_records.append({"canonical_id": entry.canonical_id, "kind": entry.kind, "locale": locale})
            elif not entry.locale_aliases[locale]:
                missing_aliases.append({
                    "alias_field": _SPEC_BY_KIND[entry.kind].alias_field,
                    "canonical_id": entry.canonical_id,
                    "kind": entry.kind,
                    "locale": locale,
                })

    def sort_key(finding: Mapping[str, str]) -> tuple[int, str, int]:
        return (_KIND_ORDER[finding["kind"]], finding["canonical_id"], LOCALES.index(finding["locale"]))

    missing_records.sort(key=sort_key)
    missing_aliases.sort(key=sort_key)
    return (
        [_copy_json_object(finding) for finding in missing_records],
        [_copy_json_object(finding) for finding in missing_aliases],
    )


def _ascii_placeholders(entries: Sequence[CanonicalEntry]) -> list[JsonObject]:
    placeholders = [
        {
            "alias": alias,
            "alias_field": _SPEC_BY_KIND[entry.kind].alias_field,
            "canonical_id": entry.canonical_id,
            "kind": entry.kind,
            "locale": locale,
        }
        for entry in entries
        for locale in LOCALES
        if locale != "enUS"
        for alias in entry.locale_aliases[locale]
        if alias.isascii() and any(character.isalpha() for character in alias)
    ]
    placeholders.sort(
        key=lambda finding: (_KIND_ORDER[finding["kind"]], finding["canonical_id"], finding["locale"], finding["alias"])
    )
    return [_copy_json_object(placeholder) for placeholder in placeholders]


def build_quality_report(
    records: Sequence[SourceRecord], entries: Sequence[CanonicalEntry], canonical_by_record: Mapping[RecordKey, str]
) -> JsonObject:
    identity_duplicates = _identity_duplicates(records, canonical_by_record)
    locale_alias_duplicates = _locale_alias_duplicates(entries)
    missing_records, missing_aliases = _missing_findings(entries)
    ascii_placeholders = _ascii_placeholders(entries)
    source_records = {
        spec.kind: {
            locale: sum(record.kind == spec.kind and record.locale == locale for record in records)
            for locale in LOCALES
        }
        for spec in DATASET_SPECS
    }
    summary = {
        "ascii_placeholders": len(ascii_placeholders),
        "duplicate_identity_aliases": len(identity_duplicates),
        "duplicate_locale_aliases": len(locale_alias_duplicates),
        "missing_locale_aliases": len(missing_aliases),
        "missing_locale_records": len(missing_records),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not any(summary.values()),
        "source_records": source_records,
        "summary": summary,
        "duplicates": {"identity_aliases": identity_duplicates, "locale_aliases": locale_alias_duplicates},
        "missing": {"locale_aliases": missing_aliases, "locale_records": missing_records},
        "ascii_placeholders": ascii_placeholders,
    }


def _run_git(repo: Path, source_name: str, *arguments: str, required: bool = True) -> str | None:
    completed = subprocess.run(["git", "-C", str(repo), *arguments], check=False, capture_output=True, encoding="utf-8")
    if completed.returncode == 0:
        return completed.stdout.strip()
    if not required:
        return None
    detail = completed.stderr.strip().splitlines()
    suffix = f": {detail[-1]}" if detail else ""
    raise CompanionDataError(f"could not read {source_name} Git metadata{suffix}")


def _git_metadata(repo: Path, source_name: str) -> JsonObject:
    commit = _run_git(repo, source_name, "rev-parse", "HEAD")
    commit_date = _run_git(repo, source_name, "show", "-s", "--format=%cI", "HEAD")
    subject = _run_git(repo, source_name, "show", "-s", "--format=%s", "HEAD")
    remote = _run_git(repo, source_name, "config", "--get", "remote.origin.url", required=False)
    metadata: JsonObject = {"commit": commit, "commit_date": commit_date, "commit_subject": subject}
    if remote:
        metadata["repository"] = remote
    return metadata


def _companion_build(companion_repo: Path) -> str:
    source_file = "D4Companion/common.props"
    path = companion_repo / Path(source_file)
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))  # noqa: S314
    except FileNotFoundError as exc:
        raise CompanionDataError(f"missing source file: {source_file}") from exc
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise CompanionDataError(f"could not parse {source_file} as UTF-8 XML: {exc}") from exc
    for element in root.iter():
        if element.tag.rsplit("}", maxsplit=1)[-1] == "Version" and element.text and element.text.strip():
            return element.text.strip()
    raise CompanionDataError(f"{source_file} does not contain a Version value")


def _companion_data_build(companion_repo: Path) -> tuple[str | None, str | None]:
    log = _run_git(companion_repo, "Diablo4Companion", "log", "-100", "--format=%H%x09%s")
    for line in (log or "").splitlines():
        commit, separator, subject = line.partition("\t")
        if separator and "data" in subject.casefold() and (match := _GAME_BUILD_PATTERN.search(subject)):
            return match.group(1), commit
    return None, None


def _d4data_build(d4data_repo: Path) -> tuple[str, str]:
    log = _run_git(d4data_repo, "d4data", "log", "-100", "--format=%H%x09%s")
    for line in (log or "").splitlines():
        commit, separator, subject = line.partition("\t")
        if separator and (match := _GAME_BUILD_PATTERN.search(subject)):
            return match.group(1), commit
    raise CompanionDataError("could not find a four-part game build in the last 100 d4data commits")


def git_file_sha256(repo: Path, source_file: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{source_file}"], check=False, capture_output=True
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise CompanionDataError(f"could not read committed source file {source_file}{suffix}")
    return hashlib.sha256(completed.stdout).hexdigest()


def collect_source_metadata(companion_repo: Path, d4data_repo: Path, records: Sequence[SourceRecord]) -> JsonObject:
    if not d4data_repo.is_dir():
        raise CompanionDataError("d4data source directory does not exist")

    companion = _git_metadata(companion_repo, "Diablo4Companion")
    companion["app_version"] = _companion_build(companion_repo)
    companion["app_version_source"] = "D4Companion/common.props"
    companion_data_build, companion_data_commit = _companion_data_build(companion_repo)
    companion["data_build"] = companion_data_build
    companion["data_build_commit"] = companion_data_commit
    companion["data_build_source"] = "git commit subject" if companion_data_build else None
    source_files = sorted({record.source_file for record in records})
    companion["files"] = {
        source_file: {
            "records": sum(record.source_file == source_file for record in records),
            "sha256": git_file_sha256(companion_repo, source_file),
        }
        for source_file in source_files
    }

    d4data = _git_metadata(d4data_repo, "d4data")
    game_build, build_commit = _d4data_build(d4data_repo)
    d4data["build"] = game_build
    d4data["build_commit"] = build_commit
    d4data["build_source"] = "git commit subject"
    return {"diablo4_companion": companion, "d4data": d4data}


def build_manifest(entries: Sequence[CanonicalEntry], sources: Mapping[str, object]) -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "locales": list(LOCALES),
        "alias_fields": {spec.kind: spec.alias_field for spec in DATASET_SPECS},
        "sources": dict(sources),
        "entries": [entry.as_json() for entry in entries],
    }


def build_companion_outputs(companion_repo: Path, d4data_repo: Path) -> tuple[JsonObject, JsonObject]:
    records = load_companion_records(companion_repo)
    entries, canonical_by_record = join_records(records)
    sources = collect_source_metadata(companion_repo, d4data_repo, records)
    manifest = build_manifest(entries, sources)
    quality_report = build_quality_report(records, entries, canonical_by_record)
    return manifest, quality_report


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2, sort_keys=True)
        output_file.write("\n")


def generate_companion_data(companion_repo: Path, d4data_repo: Path, output_dir: Path) -> GeneratedPaths:
    manifest, quality_report = build_companion_outputs(companion_repo, d4data_repo)
    if output_dir.exists() and not output_dir.is_dir():
        raise CompanionDataError("output path exists and is not a directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = GeneratedPaths(manifest=output_dir / MANIFEST_FILENAME, quality_report=output_dir / QUALITY_REPORT_FILENAME)
    _write_json(paths.manifest, manifest)
    _write_json(paths.quality_report, quality_report)
    return paths


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic enUS/zhCN alias manifest from Diablo4Companion data."
    )
    parser.add_argument(
        "--companion-repo",
        "--companion-dir",
        required=True,
        type=Path,
        help="Path to a full Diablo4Companion checkout.",
    )
    parser.add_argument(
        "--d4data-repo",
        "--d4data-dir",
        required=True,
        type=Path,
        help="Path to a full d4data checkout used for game build provenance.",
    )
    parser.add_argument("--output-dir", "-o", required=True, type=Path, help="Directory for generated JSON files.")
    parser.add_argument(
        "--allow-quality-findings",
        action="store_true",
        help="Write diagnostic output but return success even when the quality report is not clean.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        paths = generate_companion_data(args.companion_repo, args.d4data_repo, args.output_dir)
    except CompanionDataError as exc:
        parser.exit(2, f"error: {exc}\n")
    print(paths.manifest)
    print(paths.quality_report)
    quality_report = _load_json(paths.quality_report, QUALITY_REPORT_FILENAME)
    return 0 if quality_report.get("ok") is True or args.allow_quality_findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
