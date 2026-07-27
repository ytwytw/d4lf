"""Load and validate the compact seasonal source lock."""

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast
from urllib.parse import quote

from src.tools.season_data_watch.network import validate_source_url

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
D4DATA_BUILD_PATTERN = re.compile(r"\d+(?:\.\d+){2,3}")
D2CORE_BUILD_PATTERN = re.compile(r"[1-9]\d{0,11}")
EXPECTED_ROLES = {
    "d4data": "canonical_english",
    "diablo4_companion": "supplemental_bilingual",
    "d2core": "supplemental_licensed",
}


class WatchInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LockedFile:
    path: str
    sha256: str
    url: str


@dataclass(frozen=True, slots=True)
class SourceLock:
    d4data_build: str
    d4data_build_url: str
    companion_files: tuple[LockedFile, ...]
    d2core_build: str
    d2core_site_url: str
    d2core_files: tuple[LockedFile, ...]


def load_source_lock(path: Path) -> SourceLock:
    root = _load_json_object(path)
    if root.get("schema_version") != 1:
        message = "source lock schema_version must be 1"
        raise WatchInputError(message)
    sources = _object(root.get("sources"), "source lock must contain a sources object")
    if set(sources) != set(EXPECTED_ROLES):
        message = "source lock must contain exactly d4data, diablo4_companion, and d2core"
        raise WatchInputError(message)

    d4data = _source(sources, "d4data")
    companion = _source(sources, "diablo4_companion")
    d2core = _source(sources, "d2core")
    _validate_role(d4data, "d4data")
    _validate_role(companion, "diablo4_companion")
    _validate_role(d2core, "d2core")

    d4data_build = _matching_text(d4data.get("expected_build"), D4DATA_BUILD_PATTERN, "invalid d4data build")
    d4data_build_url = _source_url(d4data.get("build_url"))
    companion_raw_base = _source_url(companion.get("raw_base")).rstrip("/")
    companion_files = _companion_files(companion.get("files"), companion_raw_base)
    d2core_build = _matching_text(d2core.get("expected_build"), D2CORE_BUILD_PATTERN, "invalid D2Core build")
    d2core_site_url = _source_url(d2core.get("site_url"))
    d2core_files = _explicit_files(d2core.get("files"))
    return SourceLock(d4data_build, d4data_build_url, companion_files, d2core_build, d2core_site_url, d2core_files)


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except FileNotFoundError as error:
        message = f"source lock does not exist: {path}"
        raise WatchInputError(message) from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        message = f"source lock is not valid UTF-8 JSON: {path}"
        raise WatchInputError(message) from error
    return _object(value, "source lock must contain a JSON object")


def _source(sources: dict[str, object], name: str) -> dict[str, object]:
    return _object(sources.get(name), f"source lock contains an invalid {name} source")


def _validate_role(source: dict[str, object], name: str) -> None:
    if source.get("role") != EXPECTED_ROLES[name]:
        message = f"source lock contains an invalid {name} role"
        raise WatchInputError(message)


def _companion_files(value: object, raw_base: str) -> tuple[LockedFile, ...]:
    files = _object(value, "source lock contains invalid Diablo4Companion files")
    result = []
    for path, metadata_value in sorted(files.items()):
        if not _safe_relative_path(path):
            message = "source lock contains an unsafe Diablo4Companion path"
            raise WatchInputError(message)
        metadata = _object(metadata_value, "source lock contains invalid Diablo4Companion file metadata")
        digest = _digest(metadata.get("sha256"))
        encoded_path = "/".join(quote(part) for part in PurePosixPath(path).parts)
        result.append(LockedFile(path, digest, _source_url(f"{raw_base}/{encoded_path}")))
    return _nonempty(result, "source lock contains no Diablo4Companion files")


def _explicit_files(value: object) -> tuple[LockedFile, ...]:
    files = _object(value, "source lock contains invalid D2Core files")
    result = []
    for path, metadata_value in sorted(files.items()):
        if not _safe_relative_path(path):
            message = "source lock contains an unsafe D2Core path"
            raise WatchInputError(message)
        metadata = _object(metadata_value, "source lock contains invalid D2Core file metadata")
        result.append(LockedFile(path, _digest(metadata.get("sha256")), _source_url(metadata.get("url"))))
    return _nonempty(result, "source lock contains no D2Core files")


def _object(value: object, message: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise WatchInputError(message)
    return cast("dict[str, object]", value)


def _matching_text(value: object, pattern: re.Pattern[str], message: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise WatchInputError(message)
    return value


def _digest(value: object) -> str:
    return _matching_text(value, SHA256_PATTERN, "source lock contains an invalid SHA-256 digest")


def _source_url(value: object) -> str:
    if not isinstance(value, str):
        message = "source lock contains an invalid source URL"
        raise WatchInputError(message)
    try:
        validate_source_url(value)
    except ValueError as error:
        raise WatchInputError(str(error)) from error
    return value


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "\\" not in value
        and not path.is_absolute()
        and "." not in path.parts
        and ".." not in path.parts
    )


def _nonempty(files: list[LockedFile], message: str) -> tuple[LockedFile, ...]:
    if not files:
        raise WatchInputError(message)
    return tuple(files)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            message = f"duplicate JSON key: {key}"
            raise ValueError(message)
        result[key] = value
    return result
