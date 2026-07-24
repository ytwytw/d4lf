from __future__ import annotations

# Concrete source names and URLs make snapshot failures actionable.
# ruff: noqa: EM101, EM102
import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, cast, override
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

DEFAULT_SITE_URL = "https://www.d2core.com/"
DEFAULT_STATIC_DATA_ROOT = "https://cloudstorage.d2core.com/data/d4"
MANIFEST_FILENAME = "d2core-manifest.json"
SCHEMA_VERSION = 1
LOCALES = ("enUS", "zhCN")
AUTHORIZATION_REFERENCE = "docs/third-party-data.md#d2core"
PUBLIC_REDISTRIBUTION_STATUS = "documented"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_DISCOVERY_BUNDLES = 8

JsonObject = dict[str, object]
SnapshotKey = tuple[str, str]
Identity = tuple[str, int]


class D2CoreDataError(RuntimeError):
    pass


class BuildDiscoveryError(D2CoreDataError):
    pass


class SchemaValidationError(D2CoreDataError):
    pass


class PairValidationError(D2CoreDataError):
    pass


class SnapshotValidationError(D2CoreDataError):
    pass


class _DuplicateJsonKeyError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    root_field: str | None
    content_field: str


@dataclass(frozen=True)
class D2CoreSnapshot:
    root: Path
    manifest_path: Path
    build_version: str
    manifest: Mapping[str, object]
    payloads: Mapping[SnapshotKey, bytes]
    records: Mapping[SnapshotKey, tuple[JsonObject, ...]]


DATASET_SPECS = (
    DatasetSpec(name="affix", root_field="affix", content_field="descTpl"),
    DatasetSpec(name="aspect", root_field=None, content_field="name"),
    DatasetSpec(name="uniqueItem", root_field=None, content_field="name"),
    DatasetSpec(name="talisman", root_field=None, content_field="text"),
)
MINIMUM_RECORD_COUNTS = {"affix": 750, "aspect": 250, "uniqueItem": 200, "talisman": 500}
_SPEC_BY_NAME = {spec.name: spec for spec in DATASET_SPECS}
_BUILD_VERSION_PATTERN = re.compile(r"(?<![A-Za-z0-9_$])D4_BUILD_VERSION\s*[:=]\s*[\"']?(?P<version>\d{1,12})[\"']?")
_VALID_BUILD_VERSION_PATTERN = re.compile(r"[1-9]\d{0,11}")
_VALID_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class _ScriptSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        for name, value in attrs:
            if name.casefold() == "src" and value:
                self.sources.append(value)
                return


def _json_object(pairs: list[tuple[str, object]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str):
    raise ValueError(f"non-standard JSON value {value}")


def _decode_utf8(payload: bytes | str, source_name: str) -> str:
    if isinstance(payload, str):
        return payload.removeprefix("\ufeff")
    if not isinstance(payload, bytes):
        raise D2CoreDataError(f"{source_name}: expected bytes or text")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise D2CoreDataError(f"{source_name} is not valid UTF-8 at byte {exc.start}") from exc


def parse_json_bytes(payload: bytes, source_name: str = "<memory>") -> object:
    """Parse strict UTF-8 JSON, accepting the BOM used by D2Core affix files."""
    text = _decode_utf8(payload, source_name)
    try:
        return json.loads(text, object_pairs_hook=_json_object, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            f"{source_name} contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except (_DuplicateJsonKeyError, ValueError) as exc:
        raise SchemaValidationError(f"{source_name} contains invalid JSON: {exc}") from exc


def _dataset_spec(dataset: str) -> DatasetSpec:
    try:
        return _SPEC_BY_NAME[dataset]
    except KeyError as exc:
        raise SchemaValidationError(f"unsupported D2Core dataset: {dataset}") from exc


def _validate_locale(locale: str) -> None:
    if locale not in LOCALES:
        raise SchemaValidationError(f"unsupported D2Core locale: {locale}")


def _talisman_record(
    raw_record: object, *, section: str, source_name: str, index: int, content_field: str, source_key: str | None = None
) -> JsonObject:
    location = f"{source_name}.{section}[{index}]"
    if not isinstance(raw_record, dict):
        raise SchemaValidationError(f"{location}: expected object")
    record = cast("JsonObject", raw_record)
    key = source_key if source_key is not None else record.get("key")
    if not isinstance(key, str) or not key.strip():
        raise SchemaValidationError(f"{location}.key: expected non-empty string")
    identifier = record.get("id")
    if type(identifier) is not int or identifier < 0:
        raise SchemaValidationError(f"{location}.id: expected non-negative integer")
    content = record.get(content_field)
    if not isinstance(content, str) or not content.strip():
        raise SchemaValidationError(f"{location}.{content_field}: expected non-empty string")
    return {**record, "key": f"{section}:{key}", "sourceKey": key, "section": section, "text": content}


def _validate_talisman_payload(value: object, source_name: str) -> tuple[JsonObject, ...]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{source_name}: expected object root")
    root = cast("JsonObject", value)
    records: list[JsonObject] = []
    for section in ("charm", "seal"):
        rows = root.get(section)
        if not isinstance(rows, list):
            raise SchemaValidationError(f"{source_name}.{section}: expected array")
        records.extend(
            _talisman_record(row, section=section, source_name=source_name, index=index, content_field="name")
            for index, row in enumerate(rows)
        )

    item_sets = root.get("itemSets")
    if not isinstance(item_sets, dict):
        raise SchemaValidationError(f"{source_name}.itemSets: expected object")
    item_sets_by_key = cast("Mapping[str, object]", item_sets)
    for index, (key, row) in enumerate(sorted(item_sets_by_key.items())):
        records.append(
            _talisman_record(
                row, section="itemSets", source_name=source_name, index=index, content_field="name", source_key=key
            )
        )

    affixes = root.get("affixes")
    if not isinstance(affixes, dict):
        raise SchemaValidationError(f"{source_name}.affixes: expected object")
    for item_type in ("charm", "seal"):
        rows = affixes.get(item_type)
        if not isinstance(rows, list):
            raise SchemaValidationError(f"{source_name}.affixes.{item_type}: expected array")
        section = f"affixes.{item_type}"
        records.extend(
            _talisman_record(row, section=section, source_name=source_name, index=index, content_field="descTpl")
            for index, row in enumerate(rows)
        )
    return tuple(records)


def validate_dataset_payload(
    dataset: str, locale: str, payload: bytes, source_name: str | None = None
) -> tuple[JsonObject, ...]:
    """Parse and validate one D2Core locale payload without network or filesystem access."""
    spec = _dataset_spec(dataset)
    _validate_locale(locale)
    source_name = source_name or snapshot_filename(dataset, locale)
    value = parse_json_bytes(payload, source_name)

    if dataset == "talisman":
        return _validate_talisman_payload(value, source_name)

    root_field = spec.root_field
    if root_field is None:
        raw_records = value
    else:
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{source_name}: expected object root")
        root = cast("Mapping[str, object]", value)
        if root_field not in root:
            raise SchemaValidationError(f"{source_name}: missing root field {root_field}")
        raw_records = root[root_field]
    if not isinstance(raw_records, list):
        expected = f".{spec.root_field}" if spec.root_field else " root"
        raise SchemaValidationError(f"{source_name}{expected}: expected array")

    records: list[JsonObject] = []
    for index, raw_record in enumerate(raw_records):
        location = f"{source_name}[{index}]"
        if not isinstance(raw_record, dict):
            raise SchemaValidationError(f"{location}: expected object")
        record = cast("JsonObject", raw_record)
        key = record.get("key")
        if not isinstance(key, str) or not key.strip():
            raise SchemaValidationError(f"{location}.key: expected non-empty string")
        identifier = record.get("id")
        if type(identifier) is not int or identifier < 0:
            raise SchemaValidationError(f"{location}.id: expected non-negative integer")
        content = record.get(spec.content_field)
        if not isinstance(content, str) or not content.strip():
            raise SchemaValidationError(f"{location}.{spec.content_field}: expected non-empty string")
        records.append(record)
    return tuple(records)


def dataset_identities(records: Sequence[Mapping[str, object]]) -> Counter[Identity]:
    """Return a multiset because D2Core affixes legitimately repeat key/id pairs."""
    identities: Counter[Identity] = Counter()
    for record in records:
        key = record.get("key")
        identifier = record.get("id")
        if not isinstance(key, str) or type(identifier) is not int:
            raise SchemaValidationError("record identity requires string key and integer id")
        identities[key, identifier] += 1
    return identities


def _identity_difference(value: Counter[Identity]) -> list[JsonObject]:
    return [
        {"key": key, "id": identifier, "count": count}
        for (key, identifier), count in sorted(value.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def validate_locale_pair(
    dataset: str, en_us_records: Sequence[Mapping[str, object]], zh_cn_records: Sequence[Mapping[str, object]]
) -> None:
    """Require enUS and zhCN to contain the same key/id identity multiset."""
    _dataset_spec(dataset)
    en_us_identities = dataset_identities(en_us_records)
    zh_cn_identities = dataset_identities(zh_cn_records)
    if en_us_identities == zh_cn_identities:
        return
    missing_from_zh_cn = _identity_difference(en_us_identities - zh_cn_identities)
    missing_from_en_us = _identity_difference(zh_cn_identities - en_us_identities)
    raise PairValidationError(
        f"{dataset}: enUS/zhCN key/id identities differ; "
        f"missing_from_zhCN={missing_from_zh_cn}; missing_from_enUS={missing_from_en_us}"
    )


def extract_script_sources(html: bytes | str, source_name: str = "D2Core index") -> tuple[str, ...]:
    """Extract script sources from HTML while preserving first-seen order."""
    parser = _ScriptSourceParser()
    try:
        parser.feed(_decode_utf8(html, source_name))
        parser.close()
    except Exception as exc:
        raise BuildDiscoveryError(f"could not parse {source_name} HTML: {exc}") from exc
    return tuple(dict.fromkeys(parser.sources))


def extract_build_version(bundle: bytes | str, source_name: str = "D2Core bundle") -> str:
    """Extract one unambiguous D4_BUILD_VERSION assignment from JavaScript or text."""
    versions = sorted({
        match.group("version") for match in _BUILD_VERSION_PATTERN.finditer(_decode_utf8(bundle, source_name))
    })
    if not versions:
        raise BuildDiscoveryError(f"{source_name} does not contain D4_BUILD_VERSION")
    if len(versions) != 1:
        raise BuildDiscoveryError(f"{source_name} contains conflicting D4_BUILD_VERSION values: {versions}")
    return validate_build_version(versions[0])


def validate_build_version(build_version: str) -> str:
    if not isinstance(build_version, str) or not _VALID_BUILD_VERSION_PATTERN.fullmatch(build_version):
        raise BuildDiscoveryError("D2Core build version must contain 1-12 digits and cannot start with zero")
    return build_version


def _same_origin_javascript(site_url: str, sources: Sequence[str]) -> tuple[str, ...]:
    site = urlsplit(site_url)
    candidates = []
    for source in sources:
        absolute = urljoin(site_url, source)
        parsed = urlsplit(absolute)
        if parsed.scheme == site.scheme and parsed.netloc == site.netloc and parsed.path.casefold().endswith(".js"):
            candidates.append(absolute)
    index_bundles = [url for url in candidates if Path(urlsplit(url).path).name.casefold().startswith("index-")]
    return tuple((index_bundles or candidates)[:MAX_DISCOVERY_BUNDLES])


def _discover_build_version_with_source(fetch: Callable[[str], bytes], site_url: str) -> tuple[str, str]:
    index_payload = fetch(site_url)
    try:
        return extract_build_version(index_payload, site_url), site_url
    except BuildDiscoveryError:
        pass

    sources = extract_script_sources(index_payload, site_url)
    candidates = _same_origin_javascript(site_url, sources)
    if not candidates:
        raise BuildDiscoveryError(f"{site_url} contains no same-origin JavaScript bundle")
    errors = []
    for bundle_url in candidates:
        try:
            return extract_build_version(fetch(bundle_url), bundle_url), bundle_url
        except BuildDiscoveryError as exc:
            errors.append(str(exc))
    raise BuildDiscoveryError(f"could not discover D2Core build version: {'; '.join(errors)}")


def discover_build_version(fetch: Callable[[str], bytes], site_url: str = DEFAULT_SITE_URL) -> str:
    """Discover the current D2Core D4 build through its same-origin application bundle."""
    build_version, _ = _discover_build_version_with_source(fetch, site_url)
    return build_version


def snapshot_filename(dataset: str, locale: str) -> str:
    _dataset_spec(dataset)
    _validate_locale(locale)
    return f"{dataset}_{locale}.json"


def dataset_url(build_version: str, dataset: str, locale: str, static_data_root: str = DEFAULT_STATIC_DATA_ROOT) -> str:
    validate_build_version(build_version)
    filename = snapshot_filename(dataset, locale)
    return f"{static_data_root.rstrip('/')}/{build_version}/{filename}?env=prod&v=8"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_manifest(
    *,
    build_version: str,
    payloads: Mapping[SnapshotKey, bytes],
    records: Mapping[SnapshotKey, Sequence[Mapping[str, object]]],
    urls: Mapping[SnapshotKey, str],
    build_version_source: Mapping[str, object],
    site_url: str = DEFAULT_SITE_URL,
    static_data_root: str = DEFAULT_STATIC_DATA_ROOT,
) -> JsonObject:
    """Build deterministic snapshot provenance after payloads have been validated."""
    validate_build_version(build_version)
    expected_keys = {(spec.name, locale) for spec in DATASET_SPECS for locale in LOCALES}
    for name, values in (("payloads", payloads), ("records", records), ("urls", urls)):
        if set(values) != expected_keys:
            raise SnapshotValidationError(
                f"{name} must contain exactly the {len(expected_keys)} configured dataset/locale pairs"
            )

    files: JsonObject = {}
    for spec in DATASET_SPECS:
        for locale in LOCALES:
            key = (spec.name, locale)
            filename = snapshot_filename(*key)
            files[filename] = {
                "dataset": spec.name,
                "locale": locale,
                "records": len(records[key]),
                "sha256": sha256_bytes(payloads[key]),
                "url": urls[key],
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "build_version": build_version,
        "build_version_source": dict(build_version_source),
        "datasets": [spec.name for spec in DATASET_SPECS],
        "locales": list(LOCALES),
        "minimum_record_counts": dict(MINIMUM_RECORD_COUNTS),
        "authorization": {"public_redistribution": PUBLIC_REDISTRIBUTION_STATUS, "reference": AUTHORIZATION_REFERENCE},
        "source": {"name": "D2Core", "site_url": site_url, "static_data_root": static_data_root.rstrip("/")},
        "files": files,
    }


def _manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _stage_file(path: Path, payload: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output_file:
            output_file.write(payload)
            output_file.flush()
            os.fsync(output_file.fileno())
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def write_snapshot(output_dir: Path, manifest: Mapping[str, object], payloads: Mapping[SnapshotKey, bytes]) -> Path:
    """Stage all files and replace the manifest last so readers can detect incomplete updates."""
    _, _, files, _ = validate_snapshot_manifest(dict(manifest))
    if output_dir.exists() and not output_dir.is_dir():
        raise SnapshotValidationError(f"snapshot output path exists and is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_keys = {(spec.name, locale) for spec in DATASET_SPECS for locale in LOCALES}
    if set(payloads) != expected_keys:
        raise SnapshotValidationError("snapshot payloads do not match configured dataset/locale pairs")

    staged: list[tuple[Path, Path]] = []
    staged_manifest: Path | None = None
    try:
        for spec in DATASET_SPECS:
            for locale in LOCALES:
                key = (spec.name, locale)
                filename = snapshot_filename(*key)
                if key not in payloads:
                    raise SnapshotValidationError(f"missing snapshot payload: {filename}")
                metadata = files[filename]
                if not isinstance(metadata, dict) or metadata.get("sha256") != sha256_bytes(payloads[key]):
                    raise SnapshotValidationError(f"snapshot payload does not match manifest hash: {filename}")
                destination = output_dir / filename
                staged.append((_stage_file(destination, payloads[key]), destination))

        manifest_path = output_dir / MANIFEST_FILENAME
        staged_manifest = _stage_file(manifest_path, _manifest_bytes(manifest))
        for temporary_path, destination in staged:
            temporary_path.replace(destination)
        staged.clear()
        staged_manifest.replace(manifest_path)
        return manifest_path
    finally:
        for temporary_path, _ in staged:
            temporary_path.unlink(missing_ok=True)
        if staged_manifest is not None:
            staged_manifest.unlink(missing_ok=True)


def _read_bytes(path: Path, description: str) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise SnapshotValidationError(f"missing {description}: {path}") from exc
    except OSError as exc:
        raise SnapshotValidationError(f"could not read {description}: {path}: {exc}") from exc


def _validate_https_url(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise SnapshotValidationError(f"{location} must be a string")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SnapshotValidationError(f"{location} must be an HTTPS URL")
    return value


def _validate_manifest(manifest: object) -> tuple[JsonObject, str, JsonObject, str]:
    if not isinstance(manifest, dict):
        raise SnapshotValidationError("snapshot manifest must contain a JSON object")
    value = cast("JsonObject", manifest)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotValidationError(f"snapshot manifest schema_version must be {SCHEMA_VERSION}")
    build_version = value.get("build_version")
    if not isinstance(build_version, str):
        raise SnapshotValidationError("snapshot manifest build_version must be a string")
    try:
        validate_build_version(build_version)
    except BuildDiscoveryError as exc:
        raise SnapshotValidationError(f"invalid snapshot manifest build_version: {build_version!r}") from exc
    if value.get("datasets") != [spec.name for spec in DATASET_SPECS] or value.get("locales") != list(LOCALES):
        raise SnapshotValidationError("snapshot manifest dataset or locale declaration is not supported")
    if value.get("minimum_record_counts") != MINIMUM_RECORD_COUNTS:
        raise SnapshotValidationError("snapshot manifest minimum record-count policy is missing or changed")
    build_version_source = value.get("build_version_source")
    if not isinstance(build_version_source, dict):
        raise SnapshotValidationError("snapshot manifest build_version_source must be an object")
    source_kind = build_version_source.get("kind")
    if source_kind == "pinned":
        if set(build_version_source) != {"kind"}:
            raise SnapshotValidationError("pinned build_version_source contains unexpected fields")
    elif source_kind == "discovered":
        if set(build_version_source) != {"kind", "url"}:
            raise SnapshotValidationError("discovered build_version_source fields are invalid")
        _validate_https_url(build_version_source.get("url"), "snapshot manifest discovery URL")
    else:
        raise SnapshotValidationError("snapshot manifest build_version_source kind is invalid")
    authorization = value.get("authorization")
    expected_authorization = {
        "public_redistribution": PUBLIC_REDISTRIBUTION_STATUS,
        "reference": AUTHORIZATION_REFERENCE,
    }
    if authorization != expected_authorization:
        raise SnapshotValidationError("snapshot manifest authorization provenance is missing or changed")
    source = value.get("source")
    if not isinstance(source, dict) or source.get("name") != "D2Core":
        raise SnapshotValidationError("snapshot manifest D2Core source provenance is missing")
    _validate_https_url(source.get("site_url"), "snapshot manifest source site_url")
    static_data_root = _validate_https_url(
        source.get("static_data_root"), "snapshot manifest source static_data_root"
    ).rstrip("/")
    files = value.get("files")
    if not isinstance(files, dict):
        raise SnapshotValidationError("snapshot manifest has no files object")
    expected_filenames = {snapshot_filename(spec.name, locale) for spec in DATASET_SPECS for locale in LOCALES}
    if set(files) != expected_filenames:
        raise SnapshotValidationError("snapshot manifest files do not match configured dataset/locale pairs")
    return value, build_version, cast("JsonObject", files), static_data_root


def validate_snapshot_manifest(manifest: object) -> tuple[JsonObject, str, JsonObject, str]:
    """Validate locked snapshot metadata without reading its referenced files."""
    value, build_version, files, static_data_root = _validate_manifest(manifest)
    counts_by_dataset: dict[str, dict[str, int]] = defaultdict(dict)
    for spec in DATASET_SPECS:
        for locale in LOCALES:
            filename = snapshot_filename(spec.name, locale)
            metadata = files[filename]
            if not isinstance(metadata, dict):
                raise SnapshotValidationError(f"invalid manifest file entry: {filename}")
            if metadata.get("dataset") != spec.name or metadata.get("locale") != locale:
                raise SnapshotValidationError(f"manifest identity does not match filename: {filename}")
            expected_hash = metadata.get("sha256")
            if not isinstance(expected_hash, str) or not _VALID_SHA256_PATTERN.fullmatch(expected_hash):
                raise SnapshotValidationError(f"invalid manifest sha256: {filename}")
            expected_records = metadata.get("records")
            if type(expected_records) is not int or expected_records < 0:
                raise SnapshotValidationError(f"invalid manifest record count: {filename}")
            minimum_records = MINIMUM_RECORD_COUNTS[spec.name]
            if expected_records < minimum_records:
                raise SnapshotValidationError(
                    f"manifest record count is below the {minimum_records}-record safety floor: {filename}"
                )
            counts_by_dataset[spec.name][locale] = expected_records
            expected_url = dataset_url(build_version, spec.name, locale, static_data_root=static_data_root)
            if metadata.get("url") != expected_url:
                raise SnapshotValidationError(f"manifest URL does not match dataset identity: {filename}")
        if counts_by_dataset[spec.name]["enUS"] != counts_by_dataset[spec.name]["zhCN"]:
            raise SnapshotValidationError(f"manifest enUS/zhCN record counts differ for dataset: {spec.name}")
    return value, build_version, files, static_data_root


def load_snapshot(output_dir: Path) -> D2CoreSnapshot:
    """Read a snapshot, verify hashes and schemas, then re-check every locale pair."""
    root = output_dir.resolve()
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest = parse_json_bytes(_read_bytes(manifest_path, "D2Core manifest"), str(manifest_path))
    manifest, build_version, files, static_data_root = validate_snapshot_manifest(manifest)

    payloads: dict[SnapshotKey, bytes] = {}
    records: dict[SnapshotKey, tuple[JsonObject, ...]] = {}
    for spec in DATASET_SPECS:
        for locale in LOCALES:
            key = (spec.name, locale)
            filename = snapshot_filename(*key)
            path = output_dir / filename
            if not path.resolve().is_relative_to(root):
                raise SnapshotValidationError(f"snapshot path escapes output directory: {filename}")
            metadata = files[filename]
            if not isinstance(metadata, dict):
                raise SnapshotValidationError(f"invalid manifest file entry: {filename}")
            expected_hash = metadata.get("sha256")
            expected_records = metadata.get("records")
            if not isinstance(expected_hash, str) or not _VALID_SHA256_PATTERN.fullmatch(expected_hash):
                raise SnapshotValidationError(f"invalid manifest sha256: {filename}")
            if type(expected_records) is not int or expected_records < 0:
                raise SnapshotValidationError(f"invalid manifest record count: {filename}")
            if metadata.get("dataset") != spec.name or metadata.get("locale") != locale:
                raise SnapshotValidationError(f"manifest identity does not match filename: {filename}")
            expected_url = dataset_url(build_version, *key, static_data_root=static_data_root)
            if metadata.get("url") != expected_url:
                raise SnapshotValidationError(f"manifest URL does not match dataset identity: {filename}")

            payload = _read_bytes(path, "D2Core snapshot")
            actual_hash = sha256_bytes(payload)
            if actual_hash != expected_hash:
                raise SnapshotValidationError(
                    f"snapshot sha256 mismatch: {filename}: expected {expected_hash}, got {actual_hash}"
                )
            parsed_records = validate_dataset_payload(spec.name, locale, payload, filename)
            if len(parsed_records) != expected_records:
                raise SnapshotValidationError(
                    f"snapshot record count mismatch: {filename}: expected {expected_records}, got {len(parsed_records)}"
                )
            payloads[key] = payload
            records[key] = parsed_records

    for spec in DATASET_SPECS:
        validate_locale_pair(spec.name, records[spec.name, "enUS"], records[spec.name, "zhCN"])
    return D2CoreSnapshot(
        root=root,
        manifest_path=manifest_path,
        build_version=build_version,
        manifest=manifest,
        payloads=payloads,
        records=records,
    )


def _default_fetch(url: str) -> bytes:
    if urlsplit(url).scheme != "https":
        raise D2CoreDataError(f"refusing non-HTTPS D2Core URL: {url}")
    request = Request(url, headers={"User-Agent": "d4lf-d2core-snapshot/1"})  # noqa: S310 - HTTPS checked above
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - HTTPS is enforced above
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise D2CoreDataError(f"D2Core response exceeds {MAX_RESPONSE_BYTES} bytes: {url}")
            return payload
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise D2CoreDataError(f"could not fetch {url}: {exc}") from exc


def _fetch_bytes(fetch: Callable[[str], bytes], url: str) -> bytes:
    payload = fetch(url)
    if not isinstance(payload, bytes):
        raise D2CoreDataError(f"fetcher returned non-bytes payload for {url}")
    return payload


def fetch_snapshot(
    output_dir: Path,
    *,
    build_version: str | None = None,
    fetch: Callable[[str], bytes] = _default_fetch,
    site_url: str = DEFAULT_SITE_URL,
    static_data_root: str = DEFAULT_STATIC_DATA_ROOT,
) -> D2CoreSnapshot:
    """Fetch, fully validate, and persist the bounded D2Core locale datasets."""
    if build_version is None:
        resolved_build, discovery_url = _discover_build_version_with_source(
            lambda url: _fetch_bytes(fetch, url), site_url
        )
        version_source: JsonObject = {"kind": "discovered", "url": discovery_url}
    else:
        resolved_build = validate_build_version(build_version)
        version_source = {"kind": "pinned"}

    payloads: dict[SnapshotKey, bytes] = {}
    records: dict[SnapshotKey, tuple[JsonObject, ...]] = {}
    urls: dict[SnapshotKey, str] = {}
    for spec in DATASET_SPECS:
        for locale in LOCALES:
            key = (spec.name, locale)
            url = dataset_url(resolved_build, *key, static_data_root=static_data_root)
            payload = _fetch_bytes(fetch, url)
            payloads[key] = payload
            urls[key] = url
            records[key] = validate_dataset_payload(spec.name, locale, payload, url)

    for spec in DATASET_SPECS:
        validate_locale_pair(spec.name, records[spec.name, "enUS"], records[spec.name, "zhCN"])
    manifest = build_manifest(
        build_version=resolved_build,
        payloads=payloads,
        records=records,
        urls=urls,
        build_version_source=version_source,
        site_url=site_url,
        static_data_root=static_data_root,
    )
    write_snapshot(output_dir, manifest, payloads)
    return load_snapshot(output_dir)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch and validate a bounded D2Core enUS/zhCN data snapshot.")
    parser.add_argument("--output-dir", "-o", required=True, type=Path)
    parser.add_argument(
        "--build-version", help="Pinned numeric D2Core build; omit to discover it from the site bundle."
    )
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument("--static-data-root", default=DEFAULT_STATIC_DATA_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    try:
        snapshot = fetch_snapshot(
            arguments.output_dir,
            build_version=arguments.build_version,
            site_url=arguments.site_url,
            static_data_root=arguments.static_data_root,
        )
    except D2CoreDataError as exc:
        parser.exit(2, f"error: {exc}\n")
    print(snapshot.manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
