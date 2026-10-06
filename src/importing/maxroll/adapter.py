import json
import logging
from typing import TYPE_CHECKING, cast

from src.importing.contracts import ImportRequest, ImportResult, VariantMetadata
from src.importing.maxroll.constants import (
    BUILD_GUIDE_BASE_URL,
    PLANNER_API_DATA_URL,
    PLANNER_API_NAMES_DATA_URL,
    PLANNER_BASE_URL,
)
from src.importing.maxroll.data import _merge_localized_data
from src.importing.maxroll.paragon import extract_maxroll_paragon_steps
from src.importing.maxroll.planner import (
    _extract_planner_url_and_id_from_guide,
    _extract_planner_url_and_id_from_planner,
)
from src.importing.maxroll.selection import select_profiles
from src.importing.maxroll.slots import VariantSlots, add_item
from src.importing.pipeline import ExtractedBuild, ImportPipeline, StaticBuildGuideAdapter, Variant
from src.importing.web import get_with_retry, retry_importer

if TYPE_CHECKING:
    from src.type_aliases import JsonObject, JsonValue

LOGGER = logging.getLogger(__name__)
LOGGER.propagate = True


def _planner_api_url(url: str) -> str:
    if BUILD_GUIDE_BASE_URL in url:
        return _extract_planner_url_and_id_from_guide(url)[0]
    return _extract_planner_url_and_id_from_planner(url)[0]


def _load_planner_data(url: str) -> tuple[JsonObject, JsonObject]:
    response = get_with_retry(url=_planner_api_url(url))
    all_data = cast("JsonObject", response.json())
    return all_data, cast("JsonObject", json.loads(str(all_data["data"])))


def _validated_url(request: ImportRequest) -> str | None:
    url = request.url
    if PLANNER_BASE_URL not in url and BUILD_GUIDE_BASE_URL not in url:
        LOGGER.error("Invalid url, please use a maxroll build guide or maxroll planner url")
        return None
    return url


def fetch_variants_maxroll(request: ImportRequest) -> list[VariantMetadata]:
    if (url := _validated_url(request)) is None:
        return []
    LOGGER.info(f"Loading {url} for variants")
    try:
        all_data, build_data = _load_planner_data(url)
    except ConnectionError:
        LOGGER.error("Couldn't get planner")
        return []
    variants: list[VariantMetadata] = []
    profiles = cast("list[JsonObject]", build_data["profiles"])
    for profile_id, profile_data in enumerate(profiles):
        if profile_data.get("hidden"):
            continue
        variants.append(
            VariantMetadata(id=str(profile_id), name=str(profile_data.get("name") or f"Profile {profile_id + 1}"))
        )
    return variants


def _extract_profile_variant(
    *,
    profile_data: JsonObject,
    items: dict[str, JsonObject],
    mapping_data: JsonObject,
    class_name: str,
    build_header: str,
    request: ImportRequest,
) -> Variant:
    variant_name = str(profile_data.get("name") or "")
    build_name = build_header or class_name
    if variant_name:
        build_name += f"_{variant_name}"

    slots = VariantSlots()
    profile_items = cast("JsonObject", profile_data["items"])
    for item_id in profile_items.values():
        add_item(
            slots,
            items[str(item_id)],
            mapping_data=mapping_data,
            class_name=class_name,
            variant_name=variant_name,
            request=request,
        )

    return Variant(
        name=variant_name,
        affix_filters=slots.affix_filters,
        charm_filters=slots.charm_filters,
        seal_filters=slots.seal_filters,
        aspect_upgrade_filters=slots.aspect_upgrade_filters,
        paragon_steps=extract_maxroll_paragon_steps(profile_data, mapping_data),
        paragon_build_name=build_name,
        unsafe_slots=slots.unsafe,
        unsafe_charms=slots.unsafe_charms,
        unsafe_seals=slots.unsafe_seals,
    )


@retry_importer
def import_maxroll(request: ImportRequest) -> ImportResult | None:
    if (url := _validated_url(request)) is None:
        return None
    LOGGER.info(f"Loading {url}")
    if BUILD_GUIDE_BASE_URL in url:
        _, build_id, build_id_is_visible_position = _extract_planner_url_and_id_from_guide(url)
    else:
        _, build_id, build_id_is_visible_position = _extract_planner_url_and_id_from_planner(url)
    try:
        all_data, build_data = _load_planner_data(url)
    except ConnectionError:
        LOGGER.error("Couldn't get planner")
        return None
    guide_season = str(all_data.get("season", "") or "")
    profiles = cast("list[JsonObject]", build_data["profiles"])
    items = cast("dict[str, JsonObject]", build_data["items"])
    try:
        mapping_data = cast("JsonObject", get_with_retry(url=PLANNER_API_DATA_URL).json())
        names_data = cast("JsonObject", get_with_retry(url=PLANNER_API_NAMES_DATA_URL).json())
        _merge_localized_data(mapping_data=mapping_data, localized_data=names_data)
    except ConnectionError:
        LOGGER.error("Couldn't get planner data")
        return None
    attribute_descriptions = cast("dict[str, JsonValue]", mapping_data["attributeDescriptions"])
    mapping_data["attributeDescriptions"] = {k.lower(): v for k, v in attribute_descriptions.items()}
    class_name = str(all_data.get("class", "") or "")
    build_header = str(all_data.get("name", "") or class_name)
    finished_variants: list[Variant] = []
    profiles_to_extract = select_profiles(profiles, request, build_id, build_id_is_visible_position)

    for profile_key, profile_data in profiles_to_extract:
        variant = _extract_profile_variant(
            profile_data=profile_data,
            items=items,
            mapping_data=mapping_data,
            class_name=class_name,
            build_header=build_header,
            request=request,
        )
        variant.id = str(profile_key)
        finished_variants.append(variant)

    return ImportPipeline.run_result(
        adapter=StaticBuildGuideAdapter(
            url=url,
            build=ExtractedBuild(
                source_name="maxroll",
                class_name=class_name,
                build_header=build_header,
                season_number=guide_season,
                variants=finished_variants,
            ),
        ),
        request=request,
    )
