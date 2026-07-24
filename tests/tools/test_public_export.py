from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]


def _git(repo: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return process.stdout.strip()


def _assert_sanitized_git_metadata(repo: Path, *, expected_branch: str) -> None:
    git_dir = Path(_git(repo, "rev-parse", "--absolute-git-dir"))
    assert set(_git(repo, "for-each-ref", "--format=%(refname)").splitlines()) == {f"refs/heads/{expected_branch}"}
    assert not (git_dir / "FETCH_HEAD").exists()
    assert not (git_dir / "ORIG_HEAD").exists()
    assert not (git_dir / "logs").exists()
    assert not (git_dir / "refs" / "original").exists()
    assert not _git(repo, "fsck", "--full", "--no-reflogs", "--unreachable", "--no-progress")


def _write_third_party_fixture(source: Path) -> str:
    (source / "docs" / "third-party-data.md").write_text(
        "# Third-party data\n\n"
        "## D2Core\n\nPublic redistribution status: documented.\n\n"
        "## Diablo4Companion\n\nMIT License.\n\n"
        "## DiabloTools/d4data\n\nMIT License.\n",
        encoding="utf-8",
    )
    manifest = {
        "sources": {
            "d2core": {
                "authorization": {"public_redistribution": "documented", "reference": "docs/third-party-data.md#d2core"}
            },
            "d4data": {"repository": "https://github.com/DiabloTools/d4data.git"},
            "diablo4_companion": {"repository": "https://github.com/josdemmers/Diablo4Companion.git"},
        }
    }
    (source / "assets" / "catalog" / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (source / "THIRD-PARTY-NOTICES.md").write_text(
        "# Third-party notices\n\n"
        "## Diablo4Companion\n"
        "https://github.com/josdemmers/Diablo4Companion\n"
        "Copyright (c) 2022 Jos Demmers\n"
        "Permission is hereby granted\n\n"
        "## DiabloTools/d4data\n"
        "https://github.com/DiabloTools/d4data\n"
        "Copyright (c) 2023 blizzhackers\n"
        "Permission is hereby granted\n",
        encoding="utf-8",
    )
    return (
        "D2Core data source: https://www.d2core.com/\n"
        "Diablo4Companion: https://github.com/josdemmers/Diablo4Companion\n"
        "DiabloTools/d4data: https://github.com/DiabloTools/d4data\n"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell export is Windows-only")
def test_public_export_discards_source_history_identity_and_remote(tmp_path: Path) -> None:
    source = tmp_path / "private-source"
    target = tmp_path / "public-export"
    (source / "src" / "tools").mkdir(parents=True)
    (source / "scripts").mkdir()
    (source / "assets" / "catalog").mkdir(parents=True)
    (source / "docs").mkdir()

    (source / "src" / "__init__.py").write_text("", encoding="utf-8")
    (source / "src" / "tools" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(REPO_ROOT / "src" / "tools" / "public_safety.py", source / "src" / "tools")
    shutil.copy2(REPO_ROOT / "scripts" / "export_public_repo.ps1", source / "scripts")
    attribution = _write_third_party_fixture(source)
    (source / "README.md").write_text("first private revision\n" + attribution, encoding="utf-8")

    _git(source.parent, "init", "-b", "private-main", str(source))
    _git(source, "config", "user.name", "Private Source")
    _git(source, "config", "user.email", "private-source@example.invalid")
    _git(source, "add", "--all")
    _git(source, "commit", "-m", "Private initial revision")
    (source / "README.md").write_text("second private revision\n" + attribution, encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "Private second revision")
    _git(source, "remote", "add", "private", "https://example.invalid/private/repository.git")

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(source / "scripts" / "export_public_repo.ps1"),
            "-TargetPath",
            str(target),
        ],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert _git(source, "rev-list", "--all", "--count") == "2"
    assert _git(target, "rev-list", "--all", "--count") == "1"
    assert not _git(target, "remote")
    assert _git(target, "log", "-1", "--format=%an <%ae>|%cn <%ce>|%aI|%cI") == (
        "D4LF Public Release <public-release@invalid>|"
        "D4LF Public Release <public-release@invalid>|"
        "2000-01-01T00:00:00Z|2000-01-01T00:00:00Z"
    )
    assert not _git(target, "status", "--short")
    _assert_sanitized_git_metadata(target, expected_branch="main")


def test_public_export_uses_project_python_for_final_scan() -> None:
    script = (REPO_ROOT / "scripts" / "export_public_repo.ps1").read_text(encoding="utf-8")

    assert 'Invoke-Checked -Command "uv" -Arguments $releaseScanArguments' in script
    assert 'Invoke-Checked -Command "python" -Arguments $releaseScanArguments' not in script
    assert '"--no-project"' in script
    assert '"3.14"' in script


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell export is Windows-only")
def test_fork_release_preserves_only_upstream_history_and_public_identity(tmp_path: Path) -> None:
    source = tmp_path / "private-source"
    target = tmp_path / "fork-release"
    (source / "src" / "tools").mkdir(parents=True)
    (source / "scripts").mkdir()
    (source / "assets" / "catalog").mkdir(parents=True)
    (source / "docs").mkdir()

    (source / "src" / "__init__.py").write_text("", encoding="utf-8")
    (source / "src" / "tools" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(REPO_ROOT / "src" / "tools" / "public_safety.py", source / "src" / "tools")
    shutil.copy2(REPO_ROOT / "scripts" / "prepare_fork_release.ps1", source / "scripts")
    (source / ".gitattributes").write_text("/INTERNAL.md export-ignore\n", encoding="utf-8")
    (source / "INTERNAL.md").write_text("development-only context\n", encoding="utf-8")
    attribution = _write_third_party_fixture(source)
    (source / "README.md").write_text("upstream V9\n" + attribution, encoding="utf-8")

    _git(source.parent, "init", "-b", "private-main", str(source))
    _git(source, "config", "user.name", "Upstream Author")
    _git(source, "config", "user.email", "upstream@example.invalid")
    _git(source, "add", "--all")
    _git(source, "commit", "-m", "Upstream V9 base")
    _git(source, "tag", "v9.3.7")
    base_commit = _git(source, "rev-parse", "v9.3.7^{commit}")

    (source / "README.md").write_text("private development revision\n" + attribution, encoding="utf-8")
    _git(source, "config", "user.name", "Private Developer")
    _git(source, "config", "user.email", "private@example.invalid")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "Private development history")
    private_commit = _git(source, "rev-parse", "HEAD")

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(source / "scripts" / "prepare_fork_release.ps1"),
            "-TargetPath",
            str(target),
            "-AuthorName",
            "Public Publisher",
            "-AuthorEmail",
            "publisher@users.noreply.github.com",
        ],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert _git(target, "branch", "--show-current") == "zhcn-v9"
    assert _git(target, "rev-list", "--count", f"{base_commit}..HEAD") == "1"
    assert _git(target, "rev-parse", "HEAD^") == base_commit
    assert private_commit not in _git(target, "rev-list", "--all").splitlines()
    assert not _git(target, "remote")
    assert _git(target, "log", "-1", "--format=%an <%ae>|%cn <%ce>") == (
        "Public Publisher <publisher@users.noreply.github.com>|Public Publisher <publisher@users.noreply.github.com>"
    )
    assert not (target / "INTERNAL.md").exists()
    assert not _git(target, "status", "--short")
    _assert_sanitized_git_metadata(target, expected_branch="zhcn-v9")

    git_dir = Path(_git(target, "rev-parse", "--absolute-git-dir"))
    (git_dir / "FETCH_HEAD").write_text("private source path\n", encoding="utf-8")
    scan = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.tools.public_safety",
            "--fork-release",
            "--fork-base",
            base_commit,
            "--expected-branch",
            "zhcn-v9",
            "--expected-author-name",
            "Public Publisher",
            "--expected-author-email",
            "publisher@users.noreply.github.com",
        ],
        cwd=target,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert scan.returncode == 1
    assert "[git-transient-metadata] .git/FETCH_HEAD" in scan.stderr
