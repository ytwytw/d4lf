"""Discover the current D2Core data build without coupling to its browser importer."""

import re
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, cast, override
from urllib.parse import urljoin, urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_DISCOVERY_BUNDLES = 8
BUILD_VERSION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_$])D4_BUILD_VERSION\s*[:=]\s*[\"']?(?P<version>[1-9]\d{0,11})[\"']?"
)


class D2CoreDiscoveryError(RuntimeError):
    """Raised when one unambiguous D2Core build cannot be discovered."""


class _ScriptSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        source = dict(attrs).get("src")
        if source:
            self.sources.append(source)


def discover_catalog_build(fetch: Callable[[str], bytes], site_url: str) -> str:
    """Read the build constant from D2Core's index or one of its same-origin bundles."""
    index_payload = fetch(site_url)
    if version := _single_build_version(index_payload):
        return version

    parser = _ScriptSourceParser()
    try:
        parser.feed(index_payload.decode("utf-8-sig"))
        parser.close()
    except (UnicodeDecodeError, ValueError) as error:
        message = "Could not parse the D2Core index"
        raise D2CoreDiscoveryError(message) from error

    site = urlsplit(site_url)
    candidates: list[str] = []
    for source in dict.fromkeys(parser.sources):
        absolute = urljoin(site_url, source)
        parsed = urlsplit(absolute)
        if parsed.scheme == site.scheme and parsed.netloc == site.netloc and parsed.path.casefold().endswith(".js"):
            candidates.append(absolute)
    preferred = [url for url in candidates if PurePosixPath(urlsplit(url).path).name.casefold().startswith("index-")]
    versions = {
        version
        for url in (preferred or candidates)[:MAX_DISCOVERY_BUNDLES]
        if (version := _single_build_version(fetch(url)))
    }
    if len(versions) != 1:
        message = f"Could not discover one D2Core catalog build: {sorted(versions)}"
        raise D2CoreDiscoveryError(message)
    return next(iter(versions))


def _single_build_version(payload: bytes) -> str | None:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        message = "D2Core returned non-UTF-8 catalog metadata"
        raise D2CoreDiscoveryError(message) from error
    versions = {match.group("version") for match in BUILD_VERSION_PATTERN.finditer(text)}
    if len(versions) > 1:
        message = f"D2Core metadata contains conflicting catalog builds: {sorted(versions)}"
        raise D2CoreDiscoveryError(message)
    return cast("str | None", next(iter(versions), None))
