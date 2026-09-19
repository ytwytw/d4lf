"""Validate and stage the portable release before the updater touches installed files."""

import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile

REQUIRED_FILES = (
    "d4lf.exe",
    "saapi64.dll",
    "install_dll.cmd",
    "assets/lang/enUS/affixes.json",
    "assets/lang/zhCN/affixes.json",
    "assets/lang/zhCN/aspects.json",
    "assets/lang/zhCN/uniques.json",
    "assets/lang/zhCN/ui.json",
)


def stage_release(archive_path: Path, destination: Path) -> None:
    """Reject malformed archives and replace, never merge, the old staged payload."""
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as archive, TemporaryDirectory(prefix="stage-", dir=destination) as scratch:
        seen: set[str] = set()
        for member in archive.infolist():
            name = member.orig_filename
            path = PurePosixPath(name)
            windows_path = PureWindowsPath(name)
            if (
                not path.parts
                or path.parts[0] != "d4lf"
                or ".." in path.parts
                or "\\" in name
                or windows_path.drive
                or any(":" in part for part in path.parts)
                or name.casefold() in seen
            ):
                msg = f"Invalid or duplicate release archive path: {name}"
                raise ValueError(msg)
            seen.add(name.casefold())
        for filename in REQUIRED_FILES:
            member = archive.getinfo(f"d4lf/{filename}")
            if member.is_dir() or not member.file_size:
                msg = f"Missing or empty required release file: {filename}"
                raise ValueError(msg)
        archive.extractall(scratch)
        previous_payload = destination / "d4lf"
        if previous_payload.exists():
            shutil.rmtree(previous_payload)
        shutil.move(str(Path(scratch) / "d4lf"), str(previous_payload))
