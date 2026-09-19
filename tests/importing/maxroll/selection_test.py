import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.importing import ImportOptions, ImportRequest, VariantSelection
from src.importing.maxroll import fetch_variants_maxroll, import_maxroll
from src.importing.maxroll.planner import MaxrollError
from src.importing.maxroll.selection import select_profiles


@pytest.fixture
def live_selection():
    return json.loads((Path(__file__).parent / "data/minion_necromancer_s15.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("visible_index", [-1, 3, 4, 99])
def test_missing_visible_position_never_falls_back_to_raw_profile(live_selection, visible_index) -> None:
    request = ImportRequest(url=live_selection["source_url"])
    with pytest.raises(MaxrollError, match="visible profile .* no longer exists"):
        select_profiles(live_selection["profiles"], request, visible_index, True)


@pytest.mark.parametrize("active_index", [-1, 0, 4, 99])
def test_missing_or_hidden_active_profile_is_rejected(live_selection, active_index) -> None:
    request = ImportRequest(url=live_selection["source_url"])
    with pytest.raises(MaxrollError, match="active Maxroll profile is missing or hidden"):
        select_profiles(live_selection["profiles"], request, active_index, False)


@pytest.mark.parametrize("multi_build", [False, True])
@pytest.mark.parametrize("selection", [(), ("4",), ("99",), ("1", "4")])
def test_invalid_explicit_selection_is_not_silently_dropped(live_selection, multi_build, selection) -> None:
    request = ImportRequest(
        url=live_selection["source_url"],
        options=ImportOptions(multi_build=multi_build),
        variant_selection=VariantSelection(selection),
    )
    with pytest.raises(MaxrollError, match="selected Maxroll variant is missing or hidden"):
        select_profiles(live_selection["profiles"], request, 4, True)


@pytest.mark.parametrize("multi_build", [False, True])
def test_explicit_visible_identity_overrides_stale_url_selection(live_selection, multi_build) -> None:
    request = ImportRequest(
        url=live_selection["source_url"],
        options=ImportOptions(multi_build=multi_build),
        variant_selection=VariantSelection(("2",)),
    )
    selected = select_profiles(live_selection["profiles"], request, 4, True)
    assert [(index, profile["name"]) for index, profile in selected] == [(2, "Mid Game")]


def test_multiple_explicit_profiles_require_multi_build(live_selection) -> None:
    request = ImportRequest(url=live_selection["source_url"], variant_selection=VariantSelection(("1", "2")))
    with pytest.raises(MaxrollError, match="exactly one"):
        select_profiles(live_selection["profiles"], request, 4, True)


@pytest.mark.parametrize("profiles", [[], [{"name": "Hidden", "hidden": True}]])
@pytest.mark.parametrize("multi_build", [False, True])
def test_no_visible_profiles_cannot_produce_empty_success(profiles, multi_build) -> None:
    request = ImportRequest(url="https://maxroll.gg/d4/planner/test", options=ImportOptions(multi_build=multi_build))
    with pytest.raises(MaxrollError, match="no visible variants"):
        select_profiles(profiles, request, 0, False)


def test_valid_default_selection_preserves_identity(live_selection) -> None:
    request = ImportRequest(url=live_selection["source_url"])
    selected = select_profiles(live_selection["profiles"], request, 2, True)
    assert [(index, profile["name"]) for index, profile in selected] == [(3, "Mages")]
    assert select_profiles(live_selection["profiles"], request, 3, False) == selected


def test_stale_live_guide_does_not_extract_or_save_a_hidden_build(live_selection, mocker) -> None:
    mocker.patch(
        "src.importing.maxroll.adapter._extract_planner_url_and_id_from_guide",
        return_value=(live_selection["planner_api_url"], live_selection["guide_visible_position"], True),
    )
    mocker.patch(
        "src.importing.maxroll.adapter._load_planner_data",
        return_value=({}, {"profiles": live_selection["profiles"], "items": {}}),
    )
    response = mocker.Mock()
    response.json.return_value = {"items": {}, "attributeDescriptions": {}}
    mocker.patch("src.importing.maxroll.adapter.get_with_retry", return_value=response)
    extract = mocker.patch("src.importing.maxroll.adapter._extract_profile_variant")
    pipeline = mocker.patch("src.importing.maxroll.adapter.ImportPipeline.run_result")
    save = mocker.patch("src.profiles.ProfileDocumentStore.save_new")

    with pytest.raises(MaxrollError, match="visible profile 5 no longer exists"):
        import_maxroll(request=ImportRequest(url=live_selection["source_url"]))

    extract.assert_not_called()
    pipeline.assert_not_called()
    save.assert_not_called()


@pytest.mark.parametrize("multi_build", [False, True])
def test_online_minion_guide_imports_only_explicitly_selected_visible_variant(
    mock_ini_loader, mocker, multi_build
) -> None:
    request = ImportRequest(
        url="https://maxroll.gg/d4/build-guides/minion-necromancer-guide",
        options=ImportOptions(multi_build=multi_build, custom_file_name="maxroll-visible-smoke"),
    )
    visible = fetch_variants_maxroll(request=request)
    assert visible
    selected = visible[0]
    store = mocker.Mock()
    store.save_new.side_effect = lambda *, file_name, **_: SimpleNamespace(file_name=file_name)
    mocker.patch("src.profiles.ProfileDocumentStore.default", return_value=store)

    result = import_maxroll(request=request.with_variant_selection((selected.id,)))

    assert result is not None
    assert result.selected_variant == selected.name
    assert result.profile.affixes
    store.save_new.assert_called_once()


def test_online_valid_visible_planner_position_imports_correct_identity(mock_ini_loader, mocker) -> None:
    request = ImportRequest(
        url="https://maxroll.gg/d4/planner/iz19bx0q#1", options=ImportOptions(custom_file_name="maxroll-position-smoke")
    )
    visible = fetch_variants_maxroll(request=request)
    assert visible
    store = mocker.Mock()
    store.save_new.side_effect = lambda *, file_name, **_: SimpleNamespace(file_name=file_name)
    mocker.patch("src.profiles.ProfileDocumentStore.default", return_value=store)

    result = import_maxroll(request=request)

    assert result is not None
    assert result.selected_variant == visible[0].name
    assert result.profile.affixes
    store.save_new.assert_called_once()
