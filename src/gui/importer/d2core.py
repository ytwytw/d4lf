from __future__ import annotations

import dataclasses
import logging
import re
import unicodedata
from collections import defaultdict
from typing import TYPE_CHECKING, TypeGuard, cast
from urllib.parse import parse_qs, urlsplit

from selenium.webdriver.support.wait import WebDriverWait

import src.logger
from src.config.profile_models import AspectUniqueFilterModel, ItemFilterModel
from src.dataloader import Dataloader
from src.gui.importer.gui_common import (
    create_item_affix_pool,
    get_class_name,
    get_with_retry,
    match_source_affix,
    match_to_enum,
    retry_importer,
    update_mingreateraffixcount,
)
from src.gui.importer.import_pipeline import ExtractedBuild, ImportPipeline, StaticBuildGuideAdapter, Variant
from src.gui.importer.importer_config import ImportConfig
from src.item.data.affix import Affix, AffixType
from src.item.data.item_type import ItemType
from src.scripts import correct_name
from src.tools import d2core_data

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from selenium.webdriver.chromium.webdriver import ChromiumDriver

LOGGER = logging.getLogger(__name__)
LOGGER.propagate = True

D2CORE_HOSTS = {"d2core.com", "www.d2core.com"}
D2CORE_PLANNER_PATH = "/d4/planner"
D2CORE_PAGE_TIMEOUT = 20
D2CORE_CATALOG_LOCALE = "enUS"
SHARE_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
DATA_RESOURCE_BUILD_PATTERN = re.compile(
    r"/data/d4/(?P<build>\d{1,12})/(?:affix|aspect|uniqueItem)_(?:enUS|zhCN)\.json(?:[?#]|$)"
)
_D2CORE_FORMULA_PATTERN = re.compile(r"\[[^\[\]]*\]|\{[^{}]*\}")

_CLOUDBASE_READY_SCRIPT = "return Boolean(window.cloudbase && typeof window.cloudbase.callFunction === 'function');"
_RESOURCE_URLS_SCRIPT = "return performance.getEntriesByType('resource').map(entry => entry.name);"
_QUERY_BUILD_SCRIPT = """
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
      variants: variants.map(variant => ({
        name: variant && typeof variant.name === "string" ? variant.name : "",
        gear: variant && variant.gear && typeof variant.gear === "object" ? variant.gear : {}
      }))
    }
  });
}).catch(error => done({
  ok: false,
  message: error && error.message ? error.message : String(error || "Unknown D2Core error")
}));
"""


class D2CoreImportError(RuntimeError):
    pass


@dataclasses.dataclass(slots=True)
class D2CoreCatalog:
    build_version: str
    affix_aliases: dict[str, tuple[str, ...]]
    aspect_names: dict[str, str]
    unique_names: dict[str, str]


def extract_d2core_share_code(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or (parsed.hostname or "").casefold() not in D2CORE_HOSTS:
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


@retry_importer(inject_webdriver=True)
def import_d2core(config: ImportConfig, driver: ChromiumDriver | None = None):
    if driver is None:
        message = "D2Core import requires a browser driver"
        raise D2CoreImportError(message)
    url = config.url.strip().replace("\n", "")
    try:
        share_code = extract_d2core_share_code(url)
    except ValueError as error:
        LOGGER.error(str(error))
        return None

    LOGGER.info("Loading %s", url)
    driver.get(url)
    raw_build = _query_public_build(driver, share_code)
    catalog_build = _discover_catalog_build(driver)
    catalog = _load_catalog(catalog_build)

    class_name = get_class_name(str(raw_build.get("char", "")))
    if class_name == "Unknown":
        message = "D2Core returned no supported class name"
        raise D2CoreImportError(message)

    raw_variants = raw_build.get("variants")
    if not isinstance(raw_variants, list):
        message = "D2Core returned an invalid variants collection"
        raise D2CoreImportError(message)
    variants = [variant for variant in raw_variants if _variant_has_gear(variant)]
    if not variants:
        message = "No equipment was found in this D2Core build"
        raise D2CoreImportError(message)
    if len(variants) > 1:
        LOGGER.info("This D2Core build has %d equipment variants; importing all of them.", len(variants))

    extracted_variants = []
    for raw_variant in variants:
        gear = cast("dict[str, object]", raw_variant["gear"])
        extracted_variant = _build_variant_for_gear(list(gear.values()), catalog, config)
        extracted_variant.name = str(raw_variant.get("name", ""))
        if not extracted_variant.affix_filters and not extracted_variant.aspect_upgrade_filters:
            LOGGER.warning(
                "Skipping D2Core variant %r because no supported equipment data was resolved.", extracted_variant.name
            )
            continue
        extracted_variants.append(extracted_variant)
    if not extracted_variants:
        message = "No supported equipment data was resolved from this D2Core build"
        raise D2CoreImportError(message)

    return ImportPipeline.run(
        adapter=StaticBuildGuideAdapter(
            url=url,
            build=ExtractedBuild(
                source_name="d2core",
                class_name=class_name,
                build_header=str(raw_build.get("title", "")) or f"D2Core {share_code}",
                season_number=str(raw_build.get("season", "") or ""),
                variants=extracted_variants,
            ),
        ),
        config=config,
    )


def _query_public_build(driver: ChromiumDriver, share_code: str) -> dict[str, object]:
    WebDriverWait(driver, D2CORE_PAGE_TIMEOUT).until(lambda current: current.execute_script(_CLOUDBASE_READY_SCRIPT))
    response = driver.execute_async_script(_QUERY_BUILD_SCRIPT, share_code)
    if not isinstance(response, dict) or response.get("ok") is not True:
        message = response.get("message") if isinstance(response, dict) else "invalid response"
        error_message = f"Could not read this public D2Core build: {message}"
        raise D2CoreImportError(error_message)
    build = response.get("data")
    if not isinstance(build, dict):
        message = "D2Core returned an invalid build payload"
        raise D2CoreImportError(message)
    return cast("dict[str, object]", build)


def _discover_catalog_build(driver: ChromiumDriver) -> str:
    resource_urls = WebDriverWait(driver, D2CORE_PAGE_TIMEOUT).until(
        lambda current: current.execute_script(_RESOURCE_URLS_SCRIPT) or False
    )
    versions = _catalog_build_versions(resource_urls if isinstance(resource_urls, list) else [])
    if len(versions) == 1:
        return next(iter(versions))
    if len(versions) > 1:
        message = f"D2Core loaded conflicting catalog builds: {sorted(versions)}"
        raise D2CoreImportError(message)

    try:
        return d2core_data.discover_build_version(lambda resource_url: get_with_retry(resource_url).content)
    except (d2core_data.D2CoreDataError, ConnectionError) as error:
        message = "Could not discover the current D2Core catalog build"
        raise D2CoreImportError(message) from error


def _catalog_build_versions(resource_urls: Sequence[object]) -> set[str]:
    return {
        match.group("build")
        for value in resource_urls
        if isinstance(value, str) and (match := DATA_RESOURCE_BUILD_PATTERN.search(value))
    }


def _load_catalog(build_version: str) -> D2CoreCatalog:
    records: dict[str, tuple[dict[str, object], ...]] = {}
    for dataset in ("affix", "aspect", "uniqueItem"):
        url = d2core_data.dataset_url(build_version, dataset, D2CORE_CATALOG_LOCALE)
        response = get_with_retry(url)
        try:
            records[dataset] = d2core_data.validate_dataset_payload(
                dataset, D2CORE_CATALOG_LOCALE, response.content, url
            )
        except d2core_data.D2CoreDataError as error:
            message = f"Invalid D2Core {dataset} catalog for build {build_version}"
            raise D2CoreImportError(message) from error

    return D2CoreCatalog(
        build_version=build_version,
        affix_aliases=_index_affix_aliases(records["affix"]),
        aspect_names=_index_unique_values(records["aspect"], "name", "aspect"),
        unique_names=_index_unique_values(records["uniqueItem"], "name", "uniqueItem"),
    )


def _index_affix_aliases(records: Sequence[Mapping[str, object]]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for record in records:
        key = record.get("key")
        description = record.get("descTpl")
        if isinstance(key, str) and isinstance(description, str):
            aliases = set(_d2core_affix_aliases(description, key))
            resolved_description = record.get("desc")
            if isinstance(resolved_description, str):
                aliases.update(_d2core_affix_aliases(resolved_description, key))
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
        key = record.get("key")
        value = record.get(field_name)
        if isinstance(key, str) and isinstance(value, str) and value.strip():
            grouped[key].add(value.strip())

    result = {}
    for key, values in grouped.items():
        if len(values) == 1:
            result[key] = next(iter(values))
        else:
            LOGGER.warning("D2Core %s key %r is ambiguous and will not be imported.", dataset_name, key)
    return result


def _d2core_affix_aliases(description: str, source_key: str) -> tuple[str, ...]:
    cleaned = _D2CORE_FORMULA_PATTERN.sub("", unicodedata.normalize("NFKC", description))
    cleaned = "".join(character if character.isalpha() or character.isspace() else " " for character in cleaned)
    cleaned = " ".join(cleaned.split())
    aliases = {cleaned, source_key}
    if cleaned.casefold().startswith("x "):
        aliases.add(cleaned[2:])
    aliases.add(cleaned.removesuffix(" at level"))
    aliases.add(cleaned.replace("Wild Lighting", "Wild Lightning"))
    aliases.add(cleaned.replace(" Second After ", " Seconds After "))
    return tuple(sorted(alias for alias in aliases if alias))


def _variant_has_gear(variant: object) -> TypeGuard[dict[str, object]]:
    if not isinstance(variant, dict) or not isinstance(gear := variant.get("gear"), dict):
        return False
    return any(isinstance(piece, dict) for piece in gear.values())


def _build_variant_for_gear(gear: Sequence[object], catalog: D2CoreCatalog, config: ImportConfig) -> Variant:
    filters = []
    aspect_upgrades = []
    for raw_piece in gear:
        if not isinstance(raw_piece, dict):
            continue
        piece = cast("dict[str, object]", raw_piece)
        item_type_label = piece.get("itemType")
        item_type = (
            match_to_enum(ItemType, item_type_label, check_keys=True) if isinstance(item_type_label, str) else None
        )
        if item_type is None:
            LOGGER.warning("Skipping D2Core equipment with unknown item type %r.", item_type_label)
            continue

        unique_like = str(piece.get("type", "")).casefold() in {"unique", "uniqueitem", "mythic"}
        if not unique_like and config.import_aspect_upgrades:
            for aspect_key in (piece.get("key"), piece.get("transfiguredAspect")):
                aspect_name = _resolve_aspect(aspect_key, catalog)
                if aspect_name and aspect_name not in aspect_upgrades:
                    aspect_upgrades.append(aspect_name)

        raw_mods = piece.get("mods")
        raw_mod_list = raw_mods if isinstance(raw_mods, list) else []
        affixes = _convert_mods_to_affixes(raw_mod_list, item_type, catalog, config.import_greater_affixes)

        item_filter = ItemFilterModel(itemType=[item_type], minPower=100)
        if unique_like:
            unique_name = _resolve_unique(piece.get("key"), catalog)
            if not unique_name:
                LOGGER.warning("Skipping unresolved D2Core unique %r.", piece.get("name") or piece.get("key"))
                continue
            item_filter.unique_aspect = [AspectUniqueFilterModel(name=unique_name)]
        if not affixes and not item_filter.unique_aspect:
            LOGGER.warning("Skipping %s because it has no supported affixes.", item_type.name)
            continue
        if affixes:
            item_filter.affix_pool = create_item_affix_pool(affixes=affixes, unique_like=unique_like)
            update_mingreateraffixcount(item_filter, config.require_greater_affixes)
        filters.append(item_filter)

    return Variant(affix_filters=filters, aspect_upgrade_filters=aspect_upgrades)


def _convert_mods_to_affixes(
    raw_mods: Sequence[object], item_type: ItemType, catalog: D2CoreCatalog, import_greater_affixes: bool
) -> list[Affix]:
    resolved: dict[tuple[str, AffixType], Affix] = {}
    for raw_mod in raw_mods:
        if not isinstance(raw_mod, dict) or not isinstance(source_key := raw_mod.get("name"), str):
            continue
        if source_key.casefold().startswith("tempered_"):
            continue
        aliases = catalog.affix_aliases.get(source_key)
        if aliases is None:
            LOGGER.warning(
                "D2Core affix key %r is not in catalog build %s; skipping it.", source_key, catalog.build_version
            )
            continue
        canonical = next(
            (matched for alias in aliases if (matched := match_source_affix(alias, item_type, D2CORE_CATALOG_LOCALE))),
            None,
        )
        if canonical is None:
            LOGGER.warning("D2Core affix %r has no exact D4LF match; skipping it.", source_key)
            continue
        affix_type = (
            AffixType.greater
            if import_greater_affixes and _raw_mod_is_greater(cast("Mapping[str, object]", raw_mod), source_key)
            else AffixType.normal
        )
        resolved[canonical, affix_type] = Affix(name=canonical, type=affix_type)
    return sorted(resolved.values(), key=lambda affix: (affix.name, affix.type.value))


def _raw_mod_is_greater(raw_mod: Mapping[str, object], source_key: str) -> bool:
    greater = raw_mod.get("greater")
    explicitly_greater = greater is True or (
        isinstance(greater, int | float) and not isinstance(greater, bool) and greater > 0
    )
    return explicitly_greater or "_greater" in source_key.casefold()


def _resolve_aspect(source_key: object, catalog: D2CoreCatalog) -> str | None:
    if not isinstance(source_key, str) or not source_key:
        return None
    source_name = catalog.aspect_names.get(source_key)
    if source_name is None:
        LOGGER.warning(
            "D2Core aspect key %r is not in catalog build %s; skipping it.", source_key, catalog.build_version
        )
        return None
    canonical = correct_name(source_name.casefold().replace("aspect", "").strip()) or ""
    if canonical in Dataloader().aspect_list:
        return canonical
    LOGGER.warning("D2Core aspect %r has no exact D4LF match; skipping it.", source_name)
    return None


def _resolve_unique(source_key: object, catalog: D2CoreCatalog) -> str | None:
    if not isinstance(source_key, str) or not source_key:
        return None
    source_name = catalog.unique_names.get(source_key)
    if source_name is None:
        return None
    canonical = correct_name(source_name.replace("\u2019", "'")) or ""
    return canonical if canonical in Dataloader().aspect_unique_dict else None


if __name__ == "__main__":
    src.logger.setup()
    from src.gui.importer.gui_common import setup_webdriver

    webdriver = setup_webdriver()
    import_d2core(
        config=ImportConfig(
            url="https://www.d2core.com/d4/planner?bd=20eK",
            import_aspect_upgrades=True,
            add_to_profiles=False,
            import_greater_affixes=True,
            require_greater_affixes=True,
            export_paragon=False,
        ),
        driver=webdriver,
    )
