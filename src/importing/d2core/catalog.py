"""Discover and load the English D2Core equipment catalogs."""

import json
import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, cast, override
from urllib.parse import urljoin, urlsplit

from selenium.webdriver.support.wait import WebDriverWait

from src.importing.web import get_with_retry

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from selenium.webdriver.remote.webdriver import WebDriver

LOGGER = logging.getLogger(__name__)
CATALOG_LOCALE = "enUS"
DEFAULT_SITE_URL = "https://www.d2core.com/"
STATIC_DATA_ROOT = "https://cloudstorage.d2core.com/data/d4"
PAGE_TIMEOUT = 20
MAX_DISCOVERY_BUNDLES = 8
RESOURCE_URLS_SCRIPT = "return performance.getEntriesByType('resource').map(entry => entry.name);"
DATA_RESOURCE_BUILD_PATTERN = re.compile(
    r"/data/d4/(?P<build>[1-9]\d{0,11})/(?:affix|aspect|uniqueItem)_(?:enUS|zhCN)\.json(?:[?#]|$)"
)
BUILD_VERSION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_$])D4_BUILD_VERSION\s*[:=]\s*[\"']?(?P<version>[1-9]\d{0,11})[\"']?"
)
FORMULA_PATTERN = re.compile(r"\[[^\[\]]*\]|\{[^{}]*\}")


class D2CoreCatalogError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class D2CoreCatalog:
    build_version: str
    affix_aliases: dict[str, tuple[str, ...]]
    aspect_names: dict[str, str]
    unique_names: dict[str, str]


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


def catalog_build_versions(resource_urls: Sequence[object]) -> set[str]:
    return {
        match.group("build")
        for value in resource_urls
        if isinstance(value, str) and (match := DATA_RESOURCE_BUILD_PATTERN.search(value))
    }


def discover_catalog_build(fetch: Callable[[str], bytes], site_url: str = DEFAULT_SITE_URL) -> str:
    index_payload = fetch(site_url)
    if version := _single_build_version(index_payload):
        return version

    parser = _ScriptSourceParser()
    try:
        parser.feed(index_payload.decode("utf-8-sig"))
        parser.close()
    except (UnicodeDecodeError, ValueError) as error:
        message = "Could not parse the D2Core index"
        raise D2CoreCatalogError(message) from error

    site = urlsplit(site_url)
    candidates = []
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
        raise D2CoreCatalogError(message)
    return next(iter(versions))


def _single_build_version(payload: bytes) -> str | None:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        message = "D2Core returned non-UTF-8 catalog metadata"
        raise D2CoreCatalogError(message) from error
    versions = {match.group("version") for match in BUILD_VERSION_PATTERN.finditer(text)}
    if len(versions) > 1:
        message = f"D2Core metadata contains conflicting catalog builds: {sorted(versions)}"
        raise D2CoreCatalogError(message)
    return next(iter(versions), None)


def dataset_url(build_version: str, dataset: str) -> str:
    if not re.fullmatch(r"[1-9]\d{0,11}", build_version):
        message = "Invalid D2Core catalog build"
        raise D2CoreCatalogError(message)
    if dataset not in {"affix", "aspect", "uniqueItem"}:
        message = f"Unsupported D2Core catalog: {dataset}"
        raise D2CoreCatalogError(message)
    return f"{STATIC_DATA_ROOT}/{build_version}/{dataset}_{CATALOG_LOCALE}.json"


def load_d2core_catalog(driver: WebDriver) -> D2CoreCatalog:
    resource_urls = WebDriverWait(driver, PAGE_TIMEOUT).until(
        lambda current: current.execute_script(RESOURCE_URLS_SCRIPT) or False
    )
    versions = catalog_build_versions(resource_urls if isinstance(resource_urls, list) else [])
    if len(versions) > 1:
        message = f"D2Core loaded conflicting catalog builds: {sorted(versions)}"
        raise D2CoreCatalogError(message)
    build_version = (
        next(iter(versions)) if versions else discover_catalog_build(lambda url: get_with_retry(url).content)
    )
    records = {
        dataset: _validated_records(dataset, get_with_retry(dataset_url(build_version, dataset)).content)
        for dataset in ("affix", "aspect", "uniqueItem")
    }
    return D2CoreCatalog(
        build_version=build_version,
        affix_aliases=_index_affix_aliases(records["affix"]),
        aspect_names=_index_unique_values(records["aspect"], "name", "aspect"),
        unique_names=_index_unique_values(records["uniqueItem"], "name", "uniqueItem"),
    )


def _validated_records(dataset: str, payload: bytes) -> tuple[dict[str, object], ...]:
    try:
        value = json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: _reject_constant(constant),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        message = f"Invalid D2Core {dataset} JSON"
        raise D2CoreCatalogError(message) from error
    raw_records = value.get("affix") if dataset == "affix" and isinstance(value, dict) else value
    if not isinstance(raw_records, list):
        message = f"Invalid D2Core {dataset} catalog root"
        raise D2CoreCatalogError(message)
    content_field = "descTpl" if dataset == "affix" else "name"
    records = []
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            message = f"Invalid D2Core {dataset} record {index}"
            raise D2CoreCatalogError(message)
        record = cast("dict[str, object]", raw_record)
        if (
            not isinstance(record.get("key"), str)
            or type(record.get("id")) is not int
            or not isinstance(record.get(content_field), str)
        ):
            message = f"Invalid D2Core {dataset} record {index}"
            raise D2CoreCatalogError(message)
        records.append(record)
    return tuple(records)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            message = f"Duplicate JSON key: {key}"
            raise ValueError(message)
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    message = f"Non-standard JSON value: {value}"
    raise ValueError(message)


def _index_affix_aliases(records: Sequence[Mapping[str, object]]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for record in records:
        key, description = record.get("key"), record.get("descTpl")
        if not isinstance(key, str) or not isinstance(description, str):
            continue
        aliases = set(d2core_affix_aliases(description, key))
        if isinstance(resolved := record.get("desc"), str):
            aliases.update(d2core_affix_aliases(resolved, key))
        grouped[key].add(tuple(sorted(aliases)))
    result = {}
    for key, aliases in grouped.items():
        if len(aliases) == 1:
            result[key] = next(iter(aliases))
        else:
            LOGGER.warning("D2Core affix key %r is ambiguous and will not be imported.", key)
    return result


def _index_unique_values(records: Sequence[Mapping[str, object]], field_name: str, dataset_name: str) -> dict[str, str]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for record in records:
        key, value = record.get("key"), record.get(field_name)
        if isinstance(key, str) and isinstance(value, str) and value.strip():
            grouped[key].add(value.strip())
    result = {}
    for key, values in grouped.items():
        if len(values) == 1:
            result[key] = next(iter(values))
        else:
            LOGGER.warning("D2Core %s key %r is ambiguous and will not be imported.", dataset_name, key)
    return result


def d2core_affix_aliases(description: str, source_key: str) -> tuple[str, ...]:
    cleaned = FORMULA_PATTERN.sub("", unicodedata.normalize("NFKC", description))
    cleaned = "".join(character if character.isalpha() or character.isspace() else " " for character in cleaned)
    cleaned = " ".join(cleaned.split())
    aliases = {cleaned, source_key}
    if cleaned.casefold().startswith("x "):
        aliases.add(cleaned[2:])
    aliases.add(cleaned.removesuffix(" at level"))
    corrected = cleaned.replace("Wild Lighting", "Wild Lightning").replace(" Second After ", " Seconds After ")
    aliases.add(corrected)
    if corrected.casefold().startswith("x "):
        aliases.add(corrected[2:])
    return tuple(sorted(alias for alias in aliases if alias))
