import pytest

from src.importing import ImportOptions, ImportRequest, ImportResult, VariantSelection
from src.importing.d2core import adapter as adapter_module
from src.importing.d2core.catalog import D2CoreCatalog
from src.importing.pipeline import Variant
from src.profiles import ProfileModel


@pytest.mark.parametrize(
    ("url", "share_code"),
    [
        ("https://www.d2core.com/d4/planner?bd=20eK", "20eK"),
        ("https://d2core.com/d4/planner/?foo=1&bd=abc_123-Z", "abc_123-Z"),
    ],
)
def test_extract_share_code_accepts_strict_planner_urls(url: str, share_code: str) -> None:
    assert adapter_module.extract_d2core_share_code(url) == share_code


@pytest.mark.parametrize(
    "url",
    [
        "https://notd2core.com/d4/planner?bd=20eK",
        "http://d2core.com/d4/planner?bd=20eK",
        "https://www.d2core.com/d4/builds?bd=20eK",
        "https://www.d2core.com/d4/planner",
        "https://www.d2core.com/d4/planner?bd=one&bd=two",
    ],
)
def test_extract_share_code_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(ValueError, match="Invalid URL|must contain"):
        adapter_module.extract_d2core_share_code(url)


def test_stable_gear_id_ignores_mapping_order() -> None:
    first = {"2": {"itemType": "Ring", "mods": [{"name": "Armor"}]}, "1": {"itemType": "Helm"}}
    second = {"1": {"itemType": "Helm"}, "2": {"mods": [{"name": "Armor"}], "itemType": "Ring"}}

    assert adapter_module._stable_gear_id(first) == adapter_module._stable_gear_id(second)
    assert adapter_module._stable_gear_id(first).startswith("gear-")


def test_parse_build_uses_provider_id_hash_fallback_and_skips_empty_gear() -> None:
    build = adapter_module._parse_build_payload({
        "title": "Firewall",
        "char": "Sorcerer",
        "season": 14,
        "variants": [
            {"id": "provider-id", "name": "Endgame", "gear": {"1": {"itemType": "Ring"}}},
            {"name": "Speedfarm", "gear": {"2": {"itemType": "Helm"}}},
            {"name": "Notes", "gear": {}},
        ],
    })

    assert build.title == "Firewall"
    assert build.class_name == "Sorcerer"
    assert build.season == "14"
    assert [variant.id for variant in build.variants] == [
        "provider-id",
        adapter_module._stable_gear_id({"2": {"itemType": "Helm"}}),
    ]
    assert [variant.name for variant in build.variants] == ["Endgame", "Speedfarm"]
    assert [variant.position for variant in build.variants] == [0, 1]


def test_parse_build_rejects_duplicate_variant_ids() -> None:
    with pytest.raises(adapter_module.D2CoreImportError, match="duplicate variant id"):
        adapter_module._parse_build_payload({
            "variants": [
                {"id": "same", "gear": {"1": {"itemType": "Ring"}}},
                {"id": "same", "gear": {"2": {"itemType": "Helm"}}},
            ]
        })


def test_fetch_variants_returns_provider_ids_and_fallback_names(mocker) -> None:
    build = adapter_module._D2CoreBuild(
        title="Firewall",
        class_name="Sorcerer",
        season="14",
        variants=(
            adapter_module._D2CoreVariant("v1", "Endgame", ({"itemType": "Ring"},)),
            adapter_module._D2CoreVariant("v2", "", ({"itemType": "Helm"},)),
        ),
    )
    mocker.patch.object(adapter_module, "_load_build", return_value=build)

    variants = adapter_module.fetch_variants_d2core.__wrapped__(
        ImportRequest("https://www.d2core.com/d4/planner?bd=20eK")
    )

    assert [(variant.id, variant.name) for variant in variants] == [("v1", "Endgame"), ("v2", "Variant 2")]


def test_single_build_import_uses_one_based_url_variant_position() -> None:
    variants = (
        adapter_module._D2CoreVariant("v1", "First", ({"itemType": "Ring"},), position=0),
        adapter_module._D2CoreVariant("v3", "Third", ({"itemType": "Helm"},), position=2),
    )

    request = ImportRequest("https://www.d2core.com/d4/planner?bd=20eK&var=3")

    assert [variant.id for variant in adapter_module._selected_variants(request, variants)] == ["v3"]


def test_single_build_import_does_not_silently_replace_empty_active_variant() -> None:
    variants = (adapter_module._D2CoreVariant("v1", "First", ({"itemType": "Ring"},), position=0),)

    request = ImportRequest("https://www.d2core.com/d4/planner?bd=20eK&var=2")

    assert adapter_module._selected_variants(request, variants) == []


def test_import_filters_selected_variant_loads_catalog_once_and_runs_pipeline(mocker) -> None:
    build = adapter_module._D2CoreBuild(
        title="Firewall",
        class_name="Sorcerer",
        season="14",
        variants=(
            adapter_module._D2CoreVariant("v1", "Endgame", ({"itemType": "Ring"},)),
            adapter_module._D2CoreVariant("v2", "Speedfarm", ({"itemType": "Helm"},)),
        ),
    )
    catalog = D2CoreCatalog("72698", {}, {}, {})
    mocker.patch.object(adapter_module, "_load_build", return_value=build)
    load_catalog = mocker.patch.object(adapter_module, "load_d2core_catalog", return_value=catalog)
    extract_variant = mocker.patch.object(
        adapter_module,
        "extract_d2core_variant",
        return_value=Variant(name="Speedfarm", aspect_upgrade_filters=["accelerating"]),
    )
    expected = ImportResult(
        source_name="d2core", selected_variant="Speedfarm", profile=ProfileModel(name="imported profile")
    )
    run_result = mocker.patch.object(adapter_module.ImportPipeline, "run_result", return_value=expected)
    request = ImportRequest(
        "https://www.d2core.com/d4/planner?bd=20eK",
        options=ImportOptions(multi_build=True),
        variant_selection=VariantSelection(("v2",)),
    )

    result = adapter_module.import_d2core.__wrapped__(request)

    assert result is expected
    load_catalog.assert_called_once_with()
    extract_variant.assert_called_once_with(({"itemType": "Helm"},), catalog, request.options, name="Speedfarm")
    extracted_build = run_result.call_args.kwargs["adapter"].build
    assert extracted_build.source_name == "d2core"
    assert extracted_build.class_name == "Sorcerer"
    assert extracted_build.variants[0].name == "Speedfarm"


def test_import_rejects_selection_without_equipment(mocker) -> None:
    build = adapter_module._D2CoreBuild("Firewall", "Sorcerer", "14", ())
    mocker.patch.object(adapter_module, "_load_build", return_value=build)

    with pytest.raises(adapter_module.D2CoreImportError, match="No equipment"):
        adapter_module.import_d2core.__wrapped__(ImportRequest("https://www.d2core.com/d4/planner?bd=20eK"))
