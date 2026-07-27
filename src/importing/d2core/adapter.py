"""D2Core Cloudbase adapter for profile importing."""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

from selenium.webdriver.support.wait import WebDriverWait

from src.importing.contracts import ImportRequest, ImportResult, VariantMetadata
from src.importing.d2core.catalog import D2CoreCatalogError, load_d2core_catalog
from src.importing.d2core.extraction import extract_d2core_variant
from src.importing.filters import get_class_name
from src.importing.pipeline import ExtractedBuild, ImportPipeline, StaticBuildGuideAdapter
from src.importing.web import retry_importer

if TYPE_CHECKING:
    from collections.abc import Mapping

    from selenium.webdriver.remote.webdriver import WebDriver

LOGGER = logging.getLogger(__name__)
D2CORE_HOSTS = {"d2core.com", "www.d2core.com"}
D2CORE_PLANNER_PATH = "/d4/planner"
D2CORE_PAGE_TIMEOUT = 20
SHARE_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
CLOUDBASE_READY_SCRIPT = "return Boolean(window.cloudbase && typeof window.cloudbase.callFunction === 'function');"
QUERY_BUILD_SCRIPT = """
const shareCode = arguments[0];
const done = arguments[arguments.length - 1];

window.cloudbase.callFunction({
  name: "function-planner-queryplandetail",
  data: {bd: shareCode, enableVariant: true}
}).then(response => {
  const data = response && response.result && response.result.data;
  if (!data || typeof data !== "object") {
    done({ok: false, message: "D2Core returned no public build data."});
    return;
  }
  const variants = Array.isArray(data.variants) ? data.variants : [];
  done({
    ok: true,
    data: {
      title: typeof data.title === "string" ? data.title : "",
      char: typeof data.char === "string" ? data.char : "",
      season: data.season,
      variants: variants.map(variant => {
        const rawId = variant && (variant.id ?? variant.variantId ?? variant.key);
        return {
          id: typeof rawId === "string" || typeof rawId === "number" ? String(rawId) : "",
          name: variant && typeof variant.name === "string" ? variant.name : "",
          gear: variant && variant.gear && typeof variant.gear === "object" ? variant.gear : {}
        };
      })
    }
  });
}).catch(error => done({
  ok: false,
  message: error && error.message ? error.message : String(error || "Unknown D2Core error")
}));
"""


class D2CoreImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _D2CoreVariant:
    id: str
    name: str
    gear: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class _D2CoreBuild:
    title: str
    class_name: str
    season: str
    variants: tuple[_D2CoreVariant, ...]


def extract_d2core_share_code(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() != "https" or (parsed.hostname or "").casefold() not in D2CORE_HOSTS:
        message = "Invalid URL, please use a d2core.com planner link"
        raise ValueError(message)
    if parsed.path.rstrip("/") != D2CORE_PLANNER_PATH:
        message = "Invalid URL, please use a d2core.com/d4/planner link"
        raise ValueError(message)
    share_codes = [value.strip() for value in parse_qs(parsed.query, keep_blank_values=True).get("bd", [])]
    if len(share_codes) != 1 or not SHARE_CODE_PATTERN.fullmatch(share_codes[0]):
        message = "The D2Core planner link must contain one valid bd share code"
        raise ValueError(message)
    return share_codes[0]


def _stable_gear_id(gear: Mapping[str, object]) -> str:
    normalized = json.dumps(gear, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"gear-{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


def _parse_build_payload(payload: Mapping[str, object]) -> _D2CoreBuild:
    raw_variants = payload.get("variants")
    if not isinstance(raw_variants, list):
        message = "D2Core returned an invalid variants collection"
        raise D2CoreImportError(message)
    variants = []
    seen_ids: set[str] = set()
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, dict) or not isinstance(raw_gear := raw_variant.get("gear"), dict):
            continue
        gear_mapping = cast("dict[str, object]", raw_gear)
        gear = tuple(
            cast("dict[str, object]", piece)
            for _, piece in sorted(gear_mapping.items(), key=lambda item: str(item[0]))
            if isinstance(piece, dict)
        )
        if not gear:
            continue
        raw_id = raw_variant.get("id")
        variant_id = str(raw_id).strip() if isinstance(raw_id, str | int) and not isinstance(raw_id, bool) else ""
        variant_id = variant_id or _stable_gear_id(gear_mapping)
        if variant_id in seen_ids:
            message = f"D2Core returned duplicate variant id {variant_id!r}"
            raise D2CoreImportError(message)
        seen_ids.add(variant_id)
        variants.append(_D2CoreVariant(id=variant_id, name=str(raw_variant.get("name", "") or ""), gear=gear))
    season = payload.get("season")
    return _D2CoreBuild(
        title=str(payload.get("title", "") or ""),
        class_name=str(payload.get("char", "") or ""),
        season=str(season) if isinstance(season, str | int) and not isinstance(season, bool) else "",
        variants=tuple(variants),
    )


def _query_public_build(driver: WebDriver, share_code: str) -> _D2CoreBuild:
    WebDriverWait(driver, D2CORE_PAGE_TIMEOUT).until(lambda current: current.execute_script(CLOUDBASE_READY_SCRIPT))
    response = driver.execute_async_script(QUERY_BUILD_SCRIPT, share_code)
    if not isinstance(response, dict) or response.get("ok") is not True:
        message = response.get("message") if isinstance(response, dict) else "invalid response"
        error_message = f"Could not read this public D2Core build: {message}"
        raise D2CoreImportError(error_message)
    payload = response.get("data")
    if not isinstance(payload, dict):
        message = "D2Core returned an invalid build payload"
        raise D2CoreImportError(message)
    return _parse_build_payload(cast("dict[str, object]", payload))


def _load_build(request: ImportRequest, driver: WebDriver) -> _D2CoreBuild:
    share_code = extract_d2core_share_code(request.url)
    LOGGER.info("Loading %s", request.url)
    driver.get(request.url)
    return _query_public_build(driver, share_code)


def _require_driver(driver: WebDriver | None) -> WebDriver:
    if driver is None:
        message = "D2Core import requires a browser driver"
        raise D2CoreImportError(message)
    return driver


@retry_importer(inject_webdriver=True)
def fetch_variants_d2core(request: ImportRequest, driver: WebDriver | None = None) -> list[VariantMetadata]:
    build = _load_build(request, _require_driver(driver))
    return [
        VariantMetadata(id=variant.id, name=variant.name or f"Variant {index + 1}")
        for index, variant in enumerate(build.variants)
    ]


@retry_importer(inject_webdriver=True)
def import_d2core(request: ImportRequest, driver: WebDriver | None = None) -> ImportResult | None:
    driver = _require_driver(driver)
    build = _load_build(request, driver)
    variants = list(build.variants)
    if request.options.multi_build and request.variant_selection is not None:
        variants = [variant for variant in variants if variant.id in request.variant_selection]
    if not variants:
        message = "No equipment was found in this D2Core build"
        raise D2CoreImportError(message)
    try:
        catalog = load_d2core_catalog(driver)
    except D2CoreCatalogError as error:
        message = "Could not load the current D2Core catalog"
        raise D2CoreImportError(message) from error

    extracted_variants = []
    for variant in variants:
        extracted = extract_d2core_variant(variant.gear, catalog, request.options, name=variant.name)
        if not extracted.affix_filters and not extracted.aspect_upgrade_filters:
            LOGGER.warning("Skipping D2Core variant %r because no supported equipment was resolved.", variant.name)
            continue
        extracted_variants.append(extracted)
    if not extracted_variants:
        message = "No supported equipment data was resolved from this D2Core build"
        raise D2CoreImportError(message)

    class_name = get_class_name(build.class_name)
    if class_name == "Unknown":
        message = "D2Core returned no supported class name"
        raise D2CoreImportError(message)
    return ImportPipeline.run_result(
        adapter=StaticBuildGuideAdapter(
            url=request.url,
            build=ExtractedBuild(
                source_name="d2core",
                class_name=class_name,
                build_header=build.title or "D2Core",
                season_number=build.season,
                variants=extracted_variants,
            ),
        ),
        request=request,
    )
