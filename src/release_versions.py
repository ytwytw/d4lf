"""Ordering helpers for upstream and zhCN release tags."""

import re
from collections.abc import Iterable

_VERSION_RE = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<suffix>.*)$", re.IGNORECASE)
_PRERELEASE_RE = re.compile(r"(alpha|beta|rc)[._-]?(\d+)?", re.IGNORECASE)
_ZH_RELEASE_RE = re.compile(r"(?:^|[+._-])zhcn[._-](\d+)(?:$|[+._-])", re.IGNORECASE)


def version_key(version: str | None) -> tuple[int, int, int, int, int] | None:
    if not version or not (match := _VERSION_RE.fullmatch(version.strip())):
        return None
    suffix = match.group("suffix")
    prerelease = _PRERELEASE_RE.search(suffix)
    stage = 3
    sequence = 0
    if prerelease:
        stage = {"alpha": 0, "beta": 1, "rc": 2}[prerelease.group(1).casefold()]
        sequence = int(prerelease.group(2) or 0)
    elif zh_release := _ZH_RELEASE_RE.search(suffix):
        sequence = int(zh_release.group(1))
    return (int(match.group("major")), int(match.group("minor")), int(match.group("patch")), stage, sequence)


def is_newer_version(candidate: str | None, current: str | None) -> bool:
    candidate_key = version_key(candidate)
    current_key = version_key(current)
    return candidate_key is not None and current_key is not None and candidate_key > current_key


def is_prerelease(version: str) -> bool:
    normalized = version.casefold()
    return any(marker in normalized for marker in ("alpha", "beta", "rc"))


def select_latest_release(releases: Iterable[dict[str, object]]) -> dict[str, object] | None:
    def release_key(release: dict[str, object]) -> tuple[int, ...]:
        tag_name = release.get("tag_name")
        return version_key(tag_name if isinstance(tag_name, str) else None) or (-1,)

    return max((release for release in releases if not release.get("draft", False)), key=release_key, default=None)


__all__ = ["is_newer_version", "is_prerelease", "select_latest_release", "version_key"]
