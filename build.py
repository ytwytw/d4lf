import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from src import __version__
from src.tools.release_archive import archive_name, create_release_archive

EXE_NAME = "d4lf.exe"
REPO_ROOT = Path(__file__).resolve().parent


def generated_path(relative_path: str) -> Path:
    """Resolve only repository-owned output paths, rejecting redirects before any cleanup."""
    allowed = {"build", "build/main", "build/main.spec", "d4lf"}
    if relative_path not in allowed:
        message = f"Not a generated build path: {relative_path}"
        raise ValueError(message)
    candidate = REPO_ROOT / relative_path
    for path in (candidate, *candidate.parents):
        if path == REPO_ROOT:
            break
        if path.is_symlink() or path.is_junction():
            message = f"Refusing redirected build path: {path}"
            raise ValueError(message)
    if not candidate.resolve().is_relative_to(REPO_ROOT):
        message = f"Build path escapes repository: {candidate}"
        raise ValueError(message)
    return candidate


def prepare_release_directory() -> Path:
    """Preserve existing output (including user-added files) before making a fresh package."""
    release_dir = generated_path("d4lf")
    if release_dir.exists():
        backup = REPO_ROOT / f"d4lf_build_backup_{uuid4().hex}"
        release_dir.rename(backup)
        print(f"Previous release directory preserved at: {backup}")
    release_dir.mkdir()
    return release_dir


def build_environment() -> dict[str, str]:
    """Do not let unrelated applications' PATH DLLs replace Windows/Qt dependencies."""
    environment = os.environ.copy()
    if sys.platform == "win32":
        windows_dir = Path(environment["SYSTEMROOT"])
        paths = (
            Path(sys.executable).parent,
            Path(sys.base_prefix),
            Path(sys.base_prefix) / "DLLs",
            windows_dir / "System32",
            windows_dir,
        )
        environment["PATH"] = os.pathsep.join(str(path) for path in paths)
    return environment


def build(release_dir: Path) -> None:
    build_dir = generated_path("build")
    build_dir.mkdir(exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--onefile",
            f"--icon={REPO_ROOT / 'assets' / 'logo.ico'}",
            "--distpath",
            str(release_dir),
            "--specpath",
            str(build_dir),
            "--workpath",
            str(build_dir),
            "--paths",
            str(REPO_ROOT / "src"),
            str(REPO_ROOT / "src" / "main.py"),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=build_environment(),
    )
    (release_dir / "main.exe").rename(release_dir / EXE_NAME)


def clean_up() -> None:
    build_dir = generated_path("build/main")
    spec_path = generated_path("build/main.spec")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    spec_path.unlink(missing_ok=True)


def copy_additional_resources(release_dir: Path) -> None:
    for filename in ("README.md", "README.en.md", "LICENSE"):
        shutil.copy(REPO_ROOT / filename, release_dir)
    shutil.copy(REPO_ROOT / "tts/saapi64.dll", release_dir)
    shutil.copytree(
        REPO_ROOT / "assets", release_dir / "assets", ignore=shutil.ignore_patterns("last_update", "__pycache__")
    )
    shutil.copy(REPO_ROOT / "tts/install_dll.cmd", release_dir)
    for filename in ("loot-tools.zh-CN.md", "release-notes.zh-CN.md"):
        source = REPO_ROOT / "docs" / filename
        destination = release_dir / "docs" / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, destination)


def create_batch_for_consoleonly(release_dir: Path, exe_name: str) -> None:
    batch_file_path = release_dir / "d4lf-consoleonly.bat"
    with Path(batch_file_path).open("w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write('cd /d "%~dp0"\n')
        f.write(f'start "" "{exe_name}" --consoleonly\n')


def exe_replace_preflight_command(exe_name: str, attempts: int = 20) -> str:
    """PowerShell that exits 0 only when nothing holds the installed EXE, so no file is copied while it is locked."""
    return (
        f"$targetPath = Join-Path (Get-Location).Path '{exe_name}'; "
        "if (-not (Test-Path -LiteralPath $targetPath)) { exit 0 }; "
        f"for ($i = 0; $i -lt {attempts}; $i++) {{ "
        "try { [System.IO.File]::Open($targetPath, 'Open', 'ReadWrite', 'None').Dispose(); exit 0 } "
        "catch { Start-Sleep -Milliseconds 500 } }; exit 1"
    )


def create_batch_for_autoupdater(release_dir: Path, exe_name: str) -> None:
    batch_file_path = release_dir / "autoupdater.bat"
    Path(batch_file_path).write_text(
        f"""@echo off
setlocal
cd /d "%~dp0"
echo Preparing D4LF release files
"%~dp0{exe_name}" --autoupdate
set "UPDATE_RESULT=%ERRORLEVEL%"
if "%UPDATE_RESULT%"=="2" exit /b 0
if not "%UPDATE_RESULT%"=="0" exit /b %UPDATE_RESULT%
if not exist "temp_update\\d4lf\\{exe_name}" (
    echo Update payload is missing. No installed files were changed.
    exit /b 1
)
echo Closing only this installation's D4LF processes
powershell -NoProfile -NonInteractive -Command "$targetPath = Join-Path (Get-Location).Path '{exe_name}'; Get-Process -Name d4lf -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -eq $targetPath }} | Stop-Process -Force -ErrorAction Stop"
if errorlevel 1 exit /b 1
echo Checking that {exe_name} can be replaced
powershell -NoProfile -NonInteractive -Command "{exe_replace_preflight_command(exe_name)}"
if errorlevel 1 (
    echo {exe_name} is still in use or cannot be written, for example by D4LF started as administrator.
    echo Close every D4LF window, then run autoupdater.bat again. No installed files were changed.
    exit /b 1
)
echo Updating files without deleting local files
robocopy "temp_update\\d4lf" "." /E /R:2 /W:1 /XF "autoupdater.bat" /XD "temp_update" "logs"
if errorlevel 8 (
    echo Copy failed. Keep temp_update for recovery and extract the release ZIP manually.
    exit /b 1
)
echo Running postprocessing to verify the installed version
"%~dp0{exe_name}" --autoupdatepost
exit /b %ERRORLEVEL%
""",
        encoding="utf-8",
    )


def release_archive_path(label: str) -> Path:
    """Fail before the slow build when the label is unsafe or a tested archive would be replaced."""
    archive_path = REPO_ROOT / archive_name(label)
    if archive_path.exists():
        message = f"Refusing to replace existing release archive: {archive_path}"
        raise FileExistsError(message)
    return archive_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the portable D4LF release directory and verified ZIP.")
    parser.add_argument("--archive-version", default=__version__, help="label used in d4lf_v<label>.zip")
    args = parser.parse_args()
    os.chdir(REPO_ROOT)
    archive_path = release_archive_path(args.archive_version)
    print(f"Building version: {__version__}")
    clean_up()
    release_dir = prepare_release_directory()
    build(release_dir=release_dir)
    copy_additional_resources(release_dir)
    create_batch_for_consoleonly(release_dir=release_dir, exe_name=EXE_NAME)
    create_batch_for_autoupdater(release_dir=release_dir, exe_name=EXE_NAME)
    clean_up()
    print(f"Created verified release archive: {create_release_archive(release_dir, archive_path)}")
