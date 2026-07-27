import json
import typing
from types import SimpleNamespace

import pytest

from src.importing.d2core import catalog as catalog_module

if typing.TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


class _ImmediateWait:
    def __init__(self, driver, _timeout):
        self.driver = driver

    def until(self, method):
        result = method(self.driver)
        if not result:
            message = "fake wait condition did not pass"
            raise AssertionError(message)
        return result


class _ResourceDriver:
    def execute_script(self, _script):
        return ["https://cloudstorage.d2core.com/data/d4/72698/affix_zhCN.json?env=prod"]


def _response(payload) -> SimpleNamespace:
    return SimpleNamespace(content=json.dumps(payload).encode())


def test_catalog_build_versions_reads_only_catalog_resources() -> None:
    urls = [
        "https://cloudstorage.d2core.com/data/d4/72698/affix_zhCN.json?env=prod",
        "https://cloudstorage.d2core.com/data/d4/72698/uniqueItem_enUS.json",
        "https://www.d2core.com/assets/index.js",
        42,
    ]

    assert catalog_module.catalog_build_versions(urls) == {"72698"}


def test_discover_catalog_build_prefers_same_origin_index_bundle() -> None:
    payloads = {
        "https://www.d2core.com/": b'<script src="/assets/vendor.js"></script><script src="/assets/index-A.js"></script>',
        "https://www.d2core.com/assets/index-A.js": b'const D4_BUILD_VERSION = "72698";',
    }

    assert catalog_module.discover_catalog_build(payloads.__getitem__) == "72698"


def test_discover_catalog_build_rejects_conflicting_metadata() -> None:
    with pytest.raises(catalog_module.D2CoreCatalogError, match="conflicting"):
        catalog_module.discover_catalog_build(
            lambda _url: b'const D4_BUILD_VERSION = "72698"; const D4_BUILD_VERSION = "72699";'
        )


def test_affix_aliases_remove_formulas_multiplier_and_known_catalog_typos() -> None:
    aliases = catalog_module.d2core_affix_aliases("x[{VALUE}*100|%|] Wild Lighting Second After Hit", "S04_Damage_All")

    assert "Wild Lightning Seconds After Hit" in aliases
    assert "S04_Damage_All" in aliases


def test_load_catalog_uses_en_us_once_per_dataset_and_drops_ambiguous_keys(mocker) -> None:
    mocker.patch.object(catalog_module, "WebDriverWait", _ImmediateWait)
    responses = {
        "affix": _response({
            "affix": [
                {"key": "Armor", "id": 1, "descTpl": "+[{VALUE}] Armor"},
                {"key": "Ambiguous", "id": 2, "descTpl": "+[{VALUE}] Armor"},
                {"key": "Ambiguous", "id": 3, "descTpl": "+[{VALUE}] Maximum Life"},
            ]
        }),
        "aspect": _response([{"key": "AspectKey", "id": 4, "name": "Aspect of the Untarnished Blaze"}]),
        "uniqueItem": _response([{"key": "UniqueKey", "id": 5, "name": "Drognan's Anguish"}]),
    }

    def fake_get(url):
        dataset = next(name for name in responses if f"/{name}_enUS.json" in url)
        return responses[dataset]

    get_with_retry = mocker.patch.object(catalog_module, "get_with_retry", side_effect=fake_get)

    catalog = catalog_module.load_d2core_catalog(typing.cast("WebDriver", _ResourceDriver()))

    assert catalog.build_version == "72698"
    assert catalog.affix_aliases["Armor"] == ("Armor",)
    assert "Ambiguous" not in catalog.affix_aliases
    assert catalog.aspect_names == {"AspectKey": "Aspect of the Untarnished Blaze"}
    assert catalog.unique_names == {"UniqueKey": "Drognan's Anguish"}
    assert get_with_retry.call_count == 3
    assert all("_enUS.json" in call.args[0] for call in get_with_retry.call_args_list)


def test_load_catalog_without_browser_discovers_current_build(mocker) -> None:
    mocker.patch.object(catalog_module, "discover_catalog_build", return_value="72698")
    payloads = {
        "affix": {"affix": [{"key": "Armor", "id": 1, "descTpl": "+[{VALUE}] Armor"}]},
        "aspect": [{"key": "AspectKey", "id": 2, "name": "Aspect of the Untarnished Blaze"}],
        "uniqueItem": [{"key": "UniqueKey", "id": 3, "name": "Drognan's Anguish"}],
    }

    def fake_get(url):
        dataset = next(name for name in payloads if f"/{name}_enUS.json" in url)
        return _response(payloads[dataset])

    mocker.patch.object(catalog_module, "get_with_retry", side_effect=fake_get)

    catalog = catalog_module.load_d2core_catalog()

    assert catalog.build_version == "72698"


def test_catalog_validation_rejects_duplicate_json_keys() -> None:
    payload = b'{"affix":[{"key":"Armor","key":"Life","id":1,"descTpl":"Armor"}]}'

    with pytest.raises(catalog_module.D2CoreCatalogError, match="Invalid D2Core affix JSON"):
        catalog_module._validated_records("affix", payload)
