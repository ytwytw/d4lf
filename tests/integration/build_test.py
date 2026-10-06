import os
import subprocess
import sys
from pathlib import Path

import pytest

from build import (
    build,
    build_environment,
    clean_up,
    copy_additional_resources,
    create_batch_for_autoupdater,
    generated_path,
    prepare_release_directory,
)


def test_release_includes_bilingual_docs_license_and_locales_without_runtime_stamp(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("build.REPO_ROOT", tmp_path)
    for filename in (
        "README.md",
        "README.en.md",
        "LICENSE",
        "tts/saapi64.dll",
        "tts/install_dll.cmd",
        "docs/loot-tools.zh-CN.md",
        "docs/release-notes.zh-CN.md",
        "docs/agents/orchestration.zh-CN.md",
        "docs/research-notes.md",
        "docs/release-readiness-20261005.zh-CN.md",
        "docs/private-capture.png",
        "assets/lang/zhCN/ui.json",
        "assets/last_update",
    ):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(filename, encoding="utf-8")
    destination = tmp_path / "release"
    destination.mkdir()
    copy_additional_resources(destination)
    for filename in (
        "README.md",
        "README.en.md",
        "LICENSE",
        "saapi64.dll",
        "install_dll.cmd",
        "docs/loot-tools.zh-CN.md",
        "docs/release-notes.zh-CN.md",
        "assets/lang/zhCN/ui.json",
    ):
        assert (destination / filename).is_file()
    assert not (destination / "assets/last_update").exists()
    assert not (destination / "docs/agents/orchestration.zh-CN.md").exists()
    assert not (destination / "docs/research-notes.md").exists()
    assert not (destination / "docs/release-readiness-20261005.zh-CN.md").exists()
    assert not (destination / "docs/private-capture.png").exists()


def test_pyinstaller_paths_do_not_depend_on_spec_directory_or_current_directory(monkeypatch, tmp_path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    monkeypatch.setattr("build.REPO_ROOT", root)
    monkeypatch.chdir(tmp_path)
    destination = root / "d4lf"
    destination.mkdir()

    def fake_run(command: list[str], *, check: bool, cwd: Path, env: dict[str, str]) -> None:
        assert command[:3] == [sys.executable, "-m", "PyInstaller"]
        assert f"--icon={root / 'assets' / 'logo.ico'}" in command
        assert command[command.index("--distpath") + 1] == str(destination)
        assert command[command.index("--specpath") + 1] == str(root / "build")
        assert command[command.index("--workpath") + 1] == str(root / "build")
        assert command[command.index("--paths") + 1] == str(root / "src")
        assert command[-1] == str(root / "src" / "main.py")
        assert check is True
        assert cwd == root
        assert env == build_environment()
        (destination / "main.exe").write_bytes(b"built")

    monkeypatch.setattr("build.subprocess.run", fake_run)
    build(destination)
    assert (destination / "d4lf.exe").read_bytes() == b"built"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DLL search path")
def test_build_path_excludes_unrelated_dll_providers_without_changing_parent_environment(monkeypatch) -> None:
    original_path = r"C:\Codex\poppler\Library\bin;C:\AnotherApp\bin"
    monkeypatch.setenv("PATH", original_path)
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setenv("BUILD_TEST_MARKER", "preserved")
    environment = build_environment()
    assert environment["PATH"].split(os.pathsep) == [
        str(Path(sys.executable).parent),
        sys.base_prefix,
        str(Path(sys.base_prefix) / "DLLs"),
        r"C:\Windows\System32",
        r"C:\Windows",
    ]
    assert "poppler" not in environment["PATH"].lower()
    assert "AnotherApp" not in environment["PATH"]
    assert environment["BUILD_TEST_MARKER"] == "preserved"
    assert os.environ["PATH"] == original_path


def test_update_script_preserves_local_files_and_stops_on_failure(tmp_path) -> None:
    create_batch_for_autoupdater(tmp_path, "d4lf.exe")
    script = (tmp_path / "autoupdater.bat").read_text(encoding="utf-8")
    assert "/MIR" not in script
    assert "taskkill" not in script
    assert "Where-Object { $_.Path -eq $targetPath }" in script
    assert "if errorlevel 8 (" in script
    assert script.index("if errorlevel 8 (") < script.index("--autoupdatepost")
    assert 'if not "%UPDATE_RESULT%"=="0" exit /b %UPDATE_RESULT%' in script


def test_cleanup_only_removes_generated_cache_and_spec(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("build.REPO_ROOT", tmp_path)
    for name in ("custom.spec", "main.spec", "build/notes.txt", "build/main.spec", "build/main/cache.bin"):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text("preserve unless generated", encoding="utf-8")
    clean_up()
    for name in ("custom.spec", "main.spec", "build/notes.txt"):
        assert (tmp_path / name).is_file()
    assert not (tmp_path / "build/main.spec").exists()
    assert not (tmp_path / "build/main").exists()


def test_existing_release_and_foreign_files_are_backed_up(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("build.REPO_ROOT", tmp_path)
    old = tmp_path / "d4lf"
    old.mkdir()
    (old / "user-notes.txt").write_text("important", encoding="utf-8")
    release = prepare_release_directory()
    assert release == old
    assert not list(release.iterdir())
    backups = list(tmp_path.glob("d4lf_build_backup_*"))
    assert len(backups) == 1
    assert (backups[0] / "user-notes.txt").read_text(encoding="utf-8") == "important"


@pytest.mark.parametrize("name", ["../outside", ".", "custom.spec", "build/../notes"])
def test_unknown_cleanup_targets_are_refused(monkeypatch, tmp_path, name) -> None:
    monkeypatch.setattr("build.REPO_ROOT", tmp_path)
    with pytest.raises(ValueError, match="Not a generated build path"):
        generated_path(name)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction containment")
@pytest.mark.parametrize("name", ["d4lf", "build"])
def test_junction_to_external_directory_is_refused_without_changing_target(monkeypatch, tmp_path, name) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "important.txt").write_text("untouched", encoding="utf-8")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(root / name), str(outside)], capture_output=True, check=False
    )
    if result.returncode:
        pytest.skip("Junction creation unavailable")
    monkeypatch.setattr("build.REPO_ROOT", root)
    operation = prepare_release_directory if name == "d4lf" else clean_up
    with pytest.raises(ValueError, match="Refusing redirected build path"):
        operation()
    assert (outside / "important.txt").read_text(encoding="utf-8") == "untouched"
