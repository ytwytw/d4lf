from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from src.item.filter.repository import ProfileRulesRepository
from src.profiles import ProfileDocumentStore, ProfileModel

if TYPE_CHECKING:
    from src.settings import Settings


def test_repository_publishes_a_complete_rules_snapshot(tmp_path, monkeypatch) -> None:
    settings = SimpleNamespace(user_dir=tmp_path, general=SimpleNamespace(profiles=["profile"]))
    profile = ProfileModel(name="profile", aspect_upgrades=["accelerating"])
    ProfileDocumentStore(profiles_dir=tmp_path / "profiles", full_dump=False).save_new(
        file_name="profile", profile=profile, source="https://example.invalid"
    )

    def reject_default() -> ProfileDocumentStore:
        message = "repository should use the injected settings directory"
        raise AssertionError(message)

    monkeypatch.setattr(ProfileDocumentStore, "default", staticmethod(reject_default))
    repository = ProfileRulesRepository(lambda: cast("Settings", settings))

    first = repository.load_files()
    second = repository.rules

    assert first is second
    assert second.aspect_upgrade_filters == {"profile": ["accelerating"]}
    assert second.all_file_paths == (tmp_path / "profiles" / "profile.yaml",)
    assert repository.files_loaded


def test_repository_detects_profile_file_changes(tmp_path) -> None:
    settings = SimpleNamespace(user_dir=tmp_path, general=SimpleNamespace(profiles=["profile"]))
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    profile_path = profile_dir / "profile.yaml"
    profile_path.write_text("AspectUpgrades: []\n", encoding="utf-8")
    repository = ProfileRulesRepository(lambda: cast("Settings", settings))

    repository.load_files()
    assert not repository.did_files_change()
    profile_path.write_text("AspectUpgrades:\n- accelerating\n", encoding="utf-8")

    assert repository.did_files_change()


def test_repository_rejects_profile_paths_outside_profiles_directory(tmp_path) -> None:
    user_dir = tmp_path / "user"
    (user_dir / "profiles").mkdir(parents=True)
    external_path = user_dir / "external.yaml"
    ProfileDocumentStore(profiles_dir=user_dir, full_dump=False).save_new(
        file_name="external", profile=ProfileModel(name="external", aspect_upgrades=["accelerating"]), source="test"
    )
    settings = SimpleNamespace(user_dir=user_dir, general=SimpleNamespace(profiles=["../external"]))
    repository = ProfileRulesRepository(lambda: cast("Settings", settings))

    loaded = repository.load_files()

    assert loaded.aspect_upgrade_filters == {}
    assert loaded.all_file_paths == ()
    assert repository.load_failures == ("../external",)  # stays degraded instead of reading outside files
    external_path.write_text(external_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert not repository.did_files_change()


def test_skipped_profile_report_explains_the_safe_mode_once(tmp_path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "good.yaml").write_text("Affixes:\n- Ring:\n    itemType: [ring]\n", encoding="utf-8")
    (profiles / "broken.yaml").write_text("[invalid", encoding="utf-8")
    settings = SimpleNamespace(user_dir=tmp_path, general=SimpleNamespace(profiles=["good", "broken"]))
    repository = ProfileRulesRepository(lambda: cast("Settings", settings))
    reports = []
    repository.register_profile_failure_listener(reports.append)
    repository.load_files()
    repository.load_files()
    assert [report.skipped for report in reports] == [("broken",)]
    assert "will not mark unmatched items as junk or drop them" in reports[0].message
    assert "No profile rules" not in reports[0].message


def test_missing_profile_stays_degraded_until_restored_or_disabled(tmp_path, mocker) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "good.yaml").write_text("Affixes:\n- Ring:\n    itemType: [ring]\n", encoding="utf-8")
    general = SimpleNamespace(profiles=["good", "gone"])
    settings = SimpleNamespace(user_dir=tmp_path, general=general, save_value=mocker.Mock())
    repository = ProfileRulesRepository(lambda: cast("Settings", settings))
    reports = []
    repository.register_profile_failure_listener(reports.append)
    for _ in range(5):  # repeated reloads and time passing never withdraw the protection
        repository.load_files()
        assert not repository.did_files_change()
    assert repository.load_failures == ("gone",)
    settings.save_value.assert_not_called()
    assert len(reports) == 1
    assert "file missing: gone" in reports[0].message
    assert "文件缺失：gone" in reports[0].message
    assert "Restore or fix the file, or turn the profile off" in reports[0].message

    (profiles / "gone.yaml").write_text("Affixes: []\n", encoding="utf-8")
    assert repository.did_files_change()
    repository.load_files()
    assert repository.load_failures == ()
    (profiles / "gone.yaml").unlink()
    repository.load_files()
    assert repository.load_failures == ("gone",)
    general.profiles = ["good"]  # explicitly disabled by the user
    assert repository.did_files_change()
    repository.load_files()
    assert repository.load_failures == ()
