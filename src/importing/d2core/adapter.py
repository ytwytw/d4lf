"""D2Core Cloudbase adapter for profile importing."""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

from src.importing.contracts import ImportRequest, ImportResult, VariantMetadata
from src.importing.d2core.catalog import D2CoreCatalogError, load_d2core_catalog
from src.importing.d2core.client import D2CoreClientError, query_public_build
from src.importing.d2core.extraction import extract_d2core_variant
from src.importing.filters import get_class_name
from src.importing.pipeline import ExtractedBuild, ImportPipeline, StaticBuildGuideAdapter
from src.importing.web import retry_importer

if TYPE_CHECKING:
    from collections.abc import Mapping

LOGGER = logging.getLogger(__name__)
D2CORE_HOSTS = {"d2core.com", "www.d2core.com"}
D2CORE_PLANNER_PATH = "/d4/planner"
SHARE_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


class D2CoreImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _D2CoreVariant:
    id: str
    name: str
    gear: tuple[dict[str, object], ...]
    position: int = 0


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
    for position, raw_variant in enumerate(raw_variants):
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
        variants.append(
            _D2CoreVariant(id=variant_id, name=str(raw_variant.get("name", "") or ""), gear=gear, position=position)
        )
    season = payload.get("season")
    return _D2CoreBuild(
        title=str(payload.get("title", "") or ""),
        class_name=str(payload.get("char", "") or ""),
        season=str(season) if isinstance(season, str | int) and not isinstance(season, bool) else "",
        variants=tuple(variants),
    )


def _load_build(request: ImportRequest) -> _D2CoreBuild:
    share_code = extract_d2core_share_code(request.url)
    LOGGER.info("Loading %s", request.url)
    try:
        return _parse_build_payload(query_public_build(share_code))
    except D2CoreClientError as error:
        message = "Could not read this public D2Core build"
        raise D2CoreImportError(message) from error


def _selected_variants(request: ImportRequest, variants: tuple[_D2CoreVariant, ...]) -> list[_D2CoreVariant]:
    if request.options.multi_build:
        selection = request.variant_selection
        return [variant for variant in variants if selection is None or variant.id in selection]
    raw_active = parse_qs(urlsplit(request.url).query).get("var", ["1"])[-1]
    try:
        active_position = int(raw_active) - 1
    except ValueError:
        active_position = 0
    active_position = max(active_position, 0)
    return [variant for variant in variants if variant.position == active_position][:1]


@retry_importer
def fetch_variants_d2core(request: ImportRequest) -> list[VariantMetadata]:
    build = _load_build(request)
    return [
        VariantMetadata(id=variant.id, name=variant.name or f"Variant {index + 1}")
        for index, variant in enumerate(build.variants)
    ]


@retry_importer
def import_d2core(request: ImportRequest) -> ImportResult | None:
    build = _load_build(request)
    variants = _selected_variants(request, build.variants)
    if not variants:
        message = "No equipment was found in this D2Core build"
        raise D2CoreImportError(message)
    try:
        catalog = load_d2core_catalog()
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
