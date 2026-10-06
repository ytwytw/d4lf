"""Compare current seasonal source data with the committed source lock."""

from typing import TYPE_CHECKING, TypedDict

from src.tools.season_data_watch.discovery import D2CoreDiscoveryError, discover_catalog_build
from src.tools.season_data_watch.manifest import LockedFile, WatchInputError, load_source_lock
from src.tools.season_data_watch.network import fetch_source, sha256_hex

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_INPUT_ERROR = 2


class SourceCheckReport(TypedDict):
    ok: bool
    status: str
    exit_code: int
    locked_builds: dict[str, str]
    upstream_builds: dict[str, str]
    checked_files: list[dict[str, str]]
    issues: list[dict[str, str]]


def check_sources(source_lock: Path, *, fetch: Callable[[str], bytes] = fetch_source) -> SourceCheckReport:
    locked = load_source_lock(source_lock)
    issues: list[dict[str, str]] = []
    checked_files: list[dict[str, str]] = []

    upstream_d4data_build = _utf8_text(fetch(locked.d4data_build_url), locked.d4data_build_url)
    if upstream_d4data_build != locked.d4data_build:
        issues.append(
            _version_issue("d4data_build_drift", locked.d4data_build, upstream_d4data_build, locked.d4data_build_url)
        )
    _check_files(locked.companion_files, "diablo4_companion_file_drift", fetch, checked_files, issues)

    try:
        upstream_d2core_build = discover_catalog_build(fetch, locked.d2core_site_url)
    except D2CoreDiscoveryError as error:
        message = f"could not discover current D2Core build: {error}"
        raise WatchInputError(message) from error
    if upstream_d2core_build != locked.d2core_build:
        issues.append(
            _version_issue("d2core_build_drift", locked.d2core_build, upstream_d2core_build, locked.d2core_site_url)
        )
    _check_files(locked.d2core_files, "d2core_file_drift", fetch, checked_files, issues)
    return {
        "ok": not issues,
        "status": "ok" if not issues else "drift",
        "exit_code": EXIT_OK if not issues else EXIT_DRIFT,
        "locked_builds": {"d4data": locked.d4data_build, "d2core": locked.d2core_build},
        "upstream_builds": {"d4data": upstream_d4data_build, "d2core": upstream_d2core_build},
        "checked_files": checked_files,
        "issues": issues,
    }


def _check_files(
    files: tuple[LockedFile, ...],
    issue_code: str,
    fetch: Callable[[str], bytes],
    checked_files: list[dict[str, str]],
    issues: list[dict[str, str]],
) -> None:
    for locked_file in files:
        actual = sha256_hex(fetch(locked_file.url))
        checked_files.append({"path": locked_file.path, "sha256": actual, "url": locked_file.url})
        if actual != locked_file.sha256:
            issues.append({
                "code": issue_code,
                "path": locked_file.path,
                "expected": locked_file.sha256,
                "actual": actual,
                "url": locked_file.url,
            })


def _version_issue(code: str, expected: str, actual: str, url: str) -> dict[str, str]:
    return {"code": code, "expected": expected, "actual": actual, "url": url}


def _utf8_text(payload: bytes, url: str) -> str:
    try:
        return payload.decode("utf-8-sig").strip()
    except UnicodeDecodeError as error:
        message = f"source is not UTF-8: {url}"
        raise WatchInputError(message) from error
