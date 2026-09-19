import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from src import __version__

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


def create_batch_for_consoleonly(release_dir: Path, exe_name: str) -> None:
    batch_file_path = release_dir / "d4lf-consoleonly.bat"
    with Path(batch_file_path).open("w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write('cd /d "%~dp0"\n')
        f.write(f'start "" "{exe_name}" --consoleonly\n')


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


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    print(f"Building version: {__version__}")
    clean_up()
    release_dir = prepare_release_directory()
    build(release_dir=release_dir)
    copy_additional_resources(release_dir)
    create_batch_for_consoleonly(release_dir=release_dir, exe_name=EXE_NAME)
    create_batch_for_autoupdater(release_dir=release_dir, exe_name=EXE_NAME)
    clean_up()
