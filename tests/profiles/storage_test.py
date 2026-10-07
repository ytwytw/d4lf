"""Profile writes are atomic and re-imports never overwrite a different (user-edited) profile."""

from dataclasses import replace

import pytest

from src.importing import ImportOptions, ImportRequest
from src.importing.pipeline import ExtractedBuild, ImportPipeline, StaticBuildGuideAdapter, Variant
from src.profiles import BuildSourceModel, ItemFilterModel, ProfileDocumentStore, ProfileModel, storage
from src.profiles import document as document_module


def _profile(imported_at: str = "2026-10-06T00:00:00+00:00", min_power: int = 100) -> ProfileModel:
    return ProfileModel(
        name="imported profile",
        Affixes=[{"Ring": ItemFilterModel(min_power=min_power)}],
        source=BuildSourceModel(provider="maxroll", url="https://example.invalid/b", imported_at=imported_at),
    )


def _store(tmp_path) -> ProfileDocumentStore:
    return ProfileDocumentStore(profiles_dir=tmp_path / "profiles", full_dump=False)


def _leftovers(tmp_path) -> list[str]:
    return sorted(path.name for path in (tmp_path / "profiles").iterdir() if path.suffix == ".tmp")


def test_identical_reimport_refreshes_in_place(tmp_path) -> None:
    store = _store(tmp_path)
    first = store.save_new(file_name="maxroll_ring", profile=_profile(), source="https://example.invalid/b")
    again = store.save_new(
        file_name="maxroll_ring", profile=_profile(imported_at="2026-10-07T00:00:00+00:00"), source="x"
    )
    assert again.file_name == first.file_name == "maxroll_ring"
    assert sorted(path.name for path in store.profiles_dir.iterdir()) == ["maxroll_ring.yaml"]


@pytest.mark.parametrize("edit", ["comment", "rule"])
def test_reimport_preserves_user_edited_profile_under_a_new_name(tmp_path, edit) -> None:
    store = _store(tmp_path)
    saved = store.save_new(file_name="maxroll_ring", profile=_profile(), source="import")
    if edit == "comment":
        saved.path.write_text(saved.path.read_text(encoding="utf-8") + "# my tuning\n", encoding="utf-8")
    else:
        loaded = store.load(saved.path)
        loaded.profile.affixes[0].root["Ring"].min_power = 900
        store.save_existing(loaded=loaded, profile=loaded.profile, source="custom")
    edited = saved.path.read_bytes()

    second = store.save_new(file_name="maxroll_ring", profile=_profile(), source="import")
    third = store.save_new(file_name="maxroll_ring", profile=_profile(), source="import")

    assert second.file_name == third.file_name == "maxroll_ring_2"
    assert saved.path.read_bytes() == edited
    assert store.load(second.path).profile.affixes[0].root["Ring"].min_power == 100


def test_unreadable_existing_profile_is_preserved(tmp_path) -> None:
    store = _store(tmp_path)
    store.profiles_dir.mkdir(parents=True)
    (store.profiles_dir / "build.yaml").write_bytes(b"\xff\xfe broken")
    assert store.save_new(file_name="build", profile=_profile(), source="import").file_name == "build_2"
    assert (store.profiles_dir / "build.yaml").read_bytes() == b"\xff\xfe broken"


def test_empty_normalized_name_falls_back_to_imported(tmp_path) -> None:
    assert _store(tmp_path).save_new(file_name="'''", profile=_profile(), source="import").file_name == "imported"


@pytest.mark.parametrize("failure", ["replace", "fsync", "render"])
def test_failed_write_keeps_old_content_and_leaves_no_temp_file(tmp_path, monkeypatch, failure) -> None:
    store = _store(tmp_path)
    saved = store.save_new(file_name="build", profile=_profile(), source="import")
    loaded = store.load(saved.path)
    before = saved.path.read_bytes()

    def boom(*_args, **_kwargs):
        raise OSError(failure)

    if failure == "replace":
        monkeypatch.setattr(storage.Path, "replace", boom)
    elif failure == "fsync":
        monkeypatch.setattr(storage.os, "fsync", boom)
    else:
        monkeypatch.setattr(document_module, "to_yaml_str", boom)
    with pytest.raises(OSError, match=failure):
        store.save_existing(loaded=loaded, profile=_profile(min_power=900), source="custom")
    assert saved.path.read_bytes() == before
    assert not _leftovers(tmp_path)


def test_sharing_violation_is_retried(tmp_path, monkeypatch) -> None:
    calls = []
    original = storage.Path.replace

    def flaky(self, target):
        calls.append(target)
        if len(calls) == 1:
            msg = "in use"
            raise PermissionError(msg)
        return original(self, target)

    monkeypatch.setattr(storage.Path, "replace", flaky)
    monkeypatch.setattr(storage.time, "sleep", lambda _seconds: None)
    target = tmp_path / "profiles" / "x.yaml"
    storage.atomic_write_text(target, "a: 1\n")
    assert len(calls) == 2
    assert target.read_text(encoding="utf-8") == "a: 1\n"
    assert not _leftovers(tmp_path)


def test_pipeline_activates_the_preserving_file_name(tmp_path, mocker) -> None:
    store = _store(tmp_path)
    mocker.patch("src.profiles.ProfileDocumentStore.default", return_value=store)
    add_to_profiles = mocker.patch("src.importing.pipeline.add_to_profiles")
    build = ExtractedBuild(
        source_name="maxroll",
        class_name="Spiritborn",
        build_header="Touch",
        season_number="12",
        variants=[Variant(name="Pit", affix_filters=[ItemFilterModel(min_power=100)])],
    )
    request = ImportRequest(url="https://example.invalid/b", options=replace(ImportOptions(), add_to_profiles=True))
    first = ImportPipeline.run_result(StaticBuildGuideAdapter(url="https://example.invalid/b", build=build), request)
    user_file = store.profiles_dir / f"{first.saved_file_name}.yaml"
    user_file.write_text(user_file.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    second = ImportPipeline.run_result(StaticBuildGuideAdapter(url="https://example.invalid/b", build=build), request)

    assert second.saved_file_name == f"{first.saved_file_name}_2"
    assert user_file.read_text(encoding="utf-8").endswith("# edited\n")
    add_to_profiles.assert_called_with(second.saved_file_name)
    assert (store.profiles_dir / f"{second.saved_file_name}.yaml").is_file()
