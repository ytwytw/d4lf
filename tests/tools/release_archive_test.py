import subprocess
import sys
from zipfile import ZipFile, ZipInfo

import pytest

from src.release_payload import REQUIRED_FILES
from src.tools.release_archive import archive_name, create_release_archive, main, verify_release_archive


def _release_dir(root, *extra):
    release = root / "d4lf"
    for name in (*REQUIRED_FILES, "README.md", "assets/readme/screen.png", *extra):
        path = release / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    return release


def _raw_archive(path, names):
    # Write member names verbatim, as Windows PowerShell's inbox Compress-Archive does with backslashes.
    with ZipFile(path, "w") as archive:
        for name in names:
            member = ZipInfo("placeholder")
            member.filename = name
            archive.writestr(member, "payload")
    return path


def test_created_archive_uses_one_forward_slash_root_and_passes_updater_staging(tmp_path) -> None:
    destination = create_release_archive(_release_dir(tmp_path), tmp_path / "d4lf_v1.2.3.zip")

    with ZipFile(destination) as archive:
        names = [member.orig_filename for member in archive.infolist()]
    assert names == sorted(names)
    assert all(name.startswith("d4lf/") and "\\" not in name for name in names)
    assert {f"d4lf/{name}" for name in REQUIRED_FILES} <= set(names)
    assert "d4lf/assets/readme/screen.png" in names
    assert verify_release_archive(destination) == names
    assert not (tmp_path / "d4lf_v1.2.3.zip.partial").exists()


def test_compress_archive_backslash_layout_is_rejected(tmp_path) -> None:
    archive = _raw_archive(tmp_path / "ci.zip", [f"d4lf\\{name.replace('/', '\\')}" for name in REQUIRED_FILES])
    with pytest.raises(ValueError, match="archive path"):
        verify_release_archive(archive)


@pytest.mark.parametrize(
    "name", ["../escape", "d4lf/../../escape", "C:/escape", "other/file", "d4lf/file:stream", "d4lf/D4LF.exe"]
)
def test_malformed_payloads_keep_updater_traversal_defenses(tmp_path, name) -> None:
    archive = _raw_archive(tmp_path / "bad.zip", [*(f"d4lf/{entry}" for entry in REQUIRED_FILES), name])
    with pytest.raises(ValueError, match="archive path"):
        verify_release_archive(archive)


@pytest.mark.parametrize("missing", ["d4lf.exe", "assets/lang/zhCN/ui.json"])
def test_missing_required_file_fails_without_leaving_an_archive(tmp_path, missing) -> None:
    release = _release_dir(tmp_path)
    (release / missing).unlink()
    destination = tmp_path / "release.zip"
    with pytest.raises(ValueError, match="missing a required file"):
        create_release_archive(release, destination)
    assert not destination.exists()
    assert not (tmp_path / "release.zip.partial").exists()


def test_empty_required_file_is_rejected(tmp_path) -> None:
    release = _release_dir(tmp_path)
    (release / "saapi64.dll").write_bytes(b"")
    with pytest.raises(ValueError, match="Missing or empty required release file"):
        create_release_archive(release, tmp_path / "release.zip")


@pytest.mark.parametrize("state", ["logs/d4lf.log", "temp_update/version", "assets/last_update", "src/__pycache__/x"])
def test_runtime_state_from_a_launched_package_is_never_shipped(tmp_path, state) -> None:
    with pytest.raises(ValueError, match="runtime state"):
        create_release_archive(_release_dir(tmp_path, state), tmp_path / "release.zip")
    archive = _raw_archive(tmp_path / "state.zip", [*(f"d4lf/{entry}" for entry in REQUIRED_FILES), f"d4lf/{state}"])
    with pytest.raises(ValueError, match="runtime state"):
        verify_release_archive(archive)


def test_existing_archive_is_never_replaced(tmp_path) -> None:
    destination = tmp_path / "release.zip"
    destination.write_bytes(b"tested artifact")
    with pytest.raises(FileExistsError):
        create_release_archive(_release_dir(tmp_path), destination)
    assert destination.read_bytes() == b"tested artifact"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction containment")
def test_junction_inside_release_is_refused(tmp_path) -> None:
    release = _release_dir(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("private", encoding="utf-8")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(release / "assets" / "linked"), str(outside)],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("Junction creation unavailable")
    with pytest.raises(ValueError, match="Refusing linked path"):
        create_release_archive(release, tmp_path / "release.zip")
    assert not (tmp_path / "release.zip").exists()


@pytest.mark.parametrize("label", ["", "../1.0", "1.0/2", "1.0 beta", "-1.0", "1.0\\x"])
def test_unsafe_archive_labels_are_rejected(label) -> None:
    with pytest.raises(ValueError, match="Unsafe release archive label"):
        archive_name(label)


def test_archive_name_matches_updater_asset_lookup() -> None:
    assert archive_name("10.0.7+zhcn.3") == "d4lf_v10.0.7+zhcn.3.zip"
    assert archive_name("0123abcd") == "d4lf_v0123abcd.zip"


def test_cli_creates_and_verifies_and_reports_failures(tmp_path, capsys) -> None:
    destination = tmp_path / "out.zip"
    assert main(["create", str(_release_dir(tmp_path)), str(destination)]) == 0
    assert main(["verify", str(destination)]) == 0
    bad = _raw_archive(tmp_path / "bad.zip", ["d4lf\\d4lf.exe"])
    assert main(["verify", str(bad)]) == 1
    assert "Release archive check failed" in capsys.readouterr().err
