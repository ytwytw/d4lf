from __future__ import annotations

# Source and network errors are most useful with their concrete paths and URLs.
# ruff: noqa: EM101, EM102
import argparse
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import quote

import httpx

from src.tools import d2core_data

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

DEFAULT_D4DATA_BUILD_URL = "https://raw.githubusercontent.com/DiabloTools/d4data/master/buildVersion.txt"
DEFAULT_COMPANION_RAW_BASE = "https://raw.githubusercontent.com/josdemmers/Diablo4Companion/master"
EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_INPUT_ERROR = 2


class WatchInputError(ValueError):
    pass


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WatchInputError(f"source manifest does not exist: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WatchInputError(f"source manifest is not valid UTF-8 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WatchInputError(f"source manifest must contain a JSON object: {path}")
    return cast("dict[str, object]", value)


def _companion_source_file_hashes(manifest: Mapping[str, object]) -> dict[str, str]:
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        raise WatchInputError("source manifest has no sources object")
    companion = sources.get("diablo4_companion")
    if not isinstance(companion, dict):
        raise WatchInputError("source manifest has no Diablo4Companion file hashes")
    companion_metadata = cast("dict[str, object]", companion)
    raw_files = companion_metadata.get("files")
    if not isinstance(raw_files, dict):
        raise WatchInputError("source manifest has no Diablo4Companion file hashes")
    files = cast("dict[object, object]", raw_files)
    hashes: dict[str, str] = {}
    for path, metadata in files.items():
        if not isinstance(path, str) or not isinstance(metadata, dict):
            raise WatchInputError("source manifest contains an invalid Diablo4Companion file entry")
        digest = metadata.get("sha256")
        if not isinstance(digest, str):
            raise WatchInputError("source manifest contains an invalid Diablo4Companion file entry")
        hashes[path] = digest
    if not hashes:
        raise WatchInputError("source manifest contains no Diablo4Companion files")
    return hashes


def _d2core_source(manifest: Mapping[str, object]) -> tuple[str, str, dict[str, tuple[str, str]]] | None:
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        raise WatchInputError("source manifest has no sources object")
    source = sources.get("d2core")
    if source is None:
        return None
    try:
        source, expected_build, files, _ = d2core_data.validate_snapshot_manifest(source)
    except d2core_data.SnapshotValidationError as exc:
        raise WatchInputError(f"source manifest contains invalid D2Core metadata: {exc}") from exc
    source_metadata = source.get("source")
    site_url = source_metadata.get("site_url") if isinstance(source_metadata, dict) else None
    if not isinstance(site_url, str):
        raise WatchInputError("source manifest contains invalid D2Core source metadata")

    expected_files: dict[str, tuple[str, str]] = {}
    for path, metadata in files.items():
        metadata_object = cast("dict[str, object]", metadata) if isinstance(metadata, dict) else None
        expected_hash = metadata_object.get("sha256") if metadata_object is not None else None
        url = metadata_object.get("url") if metadata_object is not None else None
        if not isinstance(path, str) or not isinstance(expected_hash, str) or not isinstance(url, str):
            raise WatchInputError("source manifest contains an invalid D2Core file entry")
        expected_files[path] = expected_hash, url
    return expected_build, site_url, expected_files


def _default_fetch(url: str) -> bytes:
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as exc:
        raise WatchInputError(f"could not fetch {url}: {exc}") from exc


def check_sources(
    *,
    source_manifest: Path,
    d4data_build_url: str = DEFAULT_D4DATA_BUILD_URL,
    companion_raw_base: str = DEFAULT_COMPANION_RAW_BASE,
    fetch: Callable[[str], bytes] = _default_fetch,
) -> dict[str, object]:
    manifest = _load_manifest(source_manifest)
    expected_build = manifest.get("build_version")
    if not isinstance(expected_build, str) or not expected_build.strip():
        raise WatchInputError("source manifest build_version must be a non-empty string")
    expected_files = _companion_source_file_hashes(manifest)
    d2core_source = _d2core_source(manifest)

    try:
        upstream_build = fetch(d4data_build_url).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise WatchInputError(f"d4data buildVersion.txt is not UTF-8: {d4data_build_url}") from exc
    issues: list[dict[str, object]] = []
    if upstream_build != expected_build:
        issues.append({
            "code": "build_drift",
            "expected": expected_build,
            "actual": upstream_build,
            "url": d4data_build_url,
        })

    checked_files: list[dict[str, str]] = []
    for relative_path, expected_hash in sorted(expected_files.items()):
        encoded_path = "/".join(quote(part) for part in relative_path.replace("\\", "/").split("/"))
        url = f"{companion_raw_base.rstrip('/')}/{encoded_path}"
        actual_hash = hashlib.sha256(fetch(url)).hexdigest()
        checked_files.append({"path": relative_path, "sha256": actual_hash})
        if actual_hash != expected_hash:
            issues.append({
                "code": "file_drift",
                "path": relative_path,
                "expected": expected_hash,
                "actual": actual_hash,
                "url": url,
            })

    upstream_d2core_build: str | None = None
    if d2core_source is not None:
        expected_d2core_build, d2core_site_url, d2core_files = d2core_source
        try:
            upstream_d2core_build = d2core_data.discover_build_version(fetch, d2core_site_url)
        except d2core_data.D2CoreDataError as exc:
            raise WatchInputError(f"could not discover current D2Core build: {exc}") from exc
        if upstream_d2core_build != expected_d2core_build:
            issues.append({
                "code": "d2core_build_drift",
                "expected": expected_d2core_build,
                "actual": upstream_d2core_build,
                "url": d2core_site_url,
            })
        for relative_path, (expected_hash, url) in sorted(d2core_files.items()):
            actual_hash = hashlib.sha256(fetch(url)).hexdigest()
            checked_files.append({"path": f"d2core/{relative_path}", "sha256": actual_hash})
            if actual_hash != expected_hash:
                issues.append({
                    "code": "d2core_file_drift",
                    "path": relative_path,
                    "expected": expected_hash,
                    "actual": actual_hash,
                    "url": url,
                })

    return {
        "ok": not issues,
        "status": "ok" if not issues else "drift",
        "exit_code": EXIT_OK if not issues else EXIT_DRIFT,
        "expected_build": expected_build,
        "upstream_build": upstream_build,
        "upstream_d2core_build": upstream_d2core_build,
        "checked_files": checked_files,
        "issues": issues,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check locked locale inputs for upstream seasonal data drift.")
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--d4data-build-url", default=DEFAULT_D4DATA_BUILD_URL)
    parser.add_argument("--companion-raw-base", default=DEFAULT_COMPANION_RAW_BASE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = check_sources(
            source_manifest=arguments.source_manifest,
            d4data_build_url=arguments.d4data_build_url,
            companion_raw_base=arguments.companion_raw_base,
        )
    except WatchInputError as error:
        report = {
            "ok": False,
            "status": "input_error",
            "exit_code": EXIT_INPUT_ERROR,
            "issues": [{"code": "input_error", "message": str(error)}],
        }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return cast("int", report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
