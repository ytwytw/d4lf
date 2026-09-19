from zipfile import ZipFile, ZipInfo

import pytest

from src.release_payload import REQUIRED_FILES, stage_release


def _archive(path, *extra):
    with ZipFile(path, "w") as archive:
        for name in REQUIRED_FILES:
            archive.writestr("d4lf/" + name, "payload")
        for name in extra:
            member = ZipInfo("placeholder")
            member.filename = name
            archive.writestr(member, "extra")
    return path


def test_replaces_stale_payload_without_changing_installed_files(tmp_path) -> None:
    destination = tmp_path / "temp_update"
    (destination / "d4lf").mkdir(parents=True)
    (destination / "d4lf/stale.txt").write_text("old")
    installed = tmp_path / "d4lf.exe"
    installed.write_text("installed")
    stage_release(_archive(tmp_path / "release.zip"), destination)
    assert not (destination / "d4lf/stale.txt").exists()
    assert (destination / "d4lf/d4lf.exe").read_text() == "payload"
    assert installed.read_text() == "installed"


@pytest.mark.parametrize(
    "name",
    ["../escape", "d4lf/../../escape", "d4lf\\escape", "C:/escape", "other/file", "d4lf/file:stream", "d4lf/D4LF.exe"],
)
def test_rejects_malformed_archive_before_replacing_staged_payload(tmp_path, name) -> None:
    destination = tmp_path / "temp_update"
    (destination / "d4lf").mkdir(parents=True)
    (destination / "d4lf/stale.txt").write_text("preserved")
    with pytest.raises(ValueError, match="archive path"):
        stage_release(_archive(tmp_path / "release.zip", name), destination)
    assert (destination / "d4lf/stale.txt").read_text() == "preserved"


def test_missing_payload_file_is_rejected(tmp_path) -> None:
    archive_path = tmp_path / "incomplete.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("d4lf/d4lf.exe", "payload")
    with pytest.raises(KeyError):
        stage_release(archive_path, tmp_path / "temp_update")
    assert not (tmp_path / "temp_update/d4lf").exists()
