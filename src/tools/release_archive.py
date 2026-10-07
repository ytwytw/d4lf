"""Create the portable release ZIP and verify it with the updater's own staging checks."""

import argparse
import re
import sys
from operator import itemgetter
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from zipfile import ZIP_DEFLATED, BadZipFile, LargeZipFile, ZipFile

from src.release_payload import stage_release

if TYPE_CHECKING:
    from collections.abc import Iterator

ARCHIVE_ROOT = "d4lf"
_LABEL_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]*")
# A launched package writes these; shipping them would leak local state into every installation.
_RUNTIME_DIRECTORIES = frozenset({"logs", "temp_update"})
_RUNTIME_FILES = frozenset({"assets/last_update"})


def archive_name(label: str) -> str:
    """Return the asset name the updater looks for, rejecting labels unsafe in file names or URLs."""
    if not _LABEL_RE.fullmatch(label):
        msg = f"Unsafe release archive label: {label!r}"
        raise ValueError(msg)
    return f"d4lf_v{label}.zip"


def _is_runtime_state(relative: PurePosixPath) -> bool:
    return (
        relative.parts[0] in _RUNTIME_DIRECTORIES
        or "__pycache__" in relative.parts
        or relative.as_posix() in _RUNTIME_FILES
    )


def _walk(directory: Path) -> Iterator[Path]:
    # Check links before descending so a junction cannot pull outside files into the package.
    for entry in sorted(directory.iterdir()):
        if entry.is_symlink() or entry.is_junction():
            msg = f"Refusing linked path in release directory: {entry}"
            raise ValueError(msg)
        if entry.is_dir():
            yield from _walk(entry)
        elif entry.is_file():
            yield entry


def _release_members(source: Path) -> list[tuple[Path, str]]:
    if source.is_symlink() or source.is_junction() or not source.is_dir():
        msg = f"Release directory must be a real directory: {source}"
        raise ValueError(msg)
    members = []
    for path in _walk(source):
        relative = PurePosixPath(path.relative_to(source).as_posix())
        if _is_runtime_state(relative):
            msg = f"Release directory contains runtime state; rebuild it before packaging: {relative}"
            raise ValueError(msg)
        members.append((path, f"{ARCHIVE_ROOT}/{relative}"))
    return sorted(members, key=itemgetter(1))


def verify_release_archive(archive_path: Path) -> list[str]:
    """Stage a scratch copy exactly as the updater would and return the archive member names."""
    with TemporaryDirectory(prefix="d4lf-release-verify-") as scratch:
        try:
            stage_release(archive_path, Path(scratch) / "temp_update")
        except KeyError as error:
            msg = f"Release archive is missing a required file: {error}"
            raise ValueError(msg) from error
    with ZipFile(archive_path) as archive:
        names = [member.orig_filename for member in archive.infolist()]
    for name in names:
        relative = PurePosixPath(name).relative_to(ARCHIVE_ROOT)
        if relative.parts and _is_runtime_state(relative):
            msg = f"Release archive contains runtime state: {name}"
            raise ValueError(msg)
    return names


def create_release_archive(source: Path, destination: Path) -> Path:
    """Write forward-slash entries under one d4lf/ root and publish the file only after verification."""
    if destination.exists():
        msg = f"Refusing to replace existing release archive: {destination}"
        raise FileExistsError(msg)
    members = _release_members(source)
    partial = destination.with_name(destination.name + ".partial")
    partial.unlink(missing_ok=True)
    try:
        with ZipFile(partial, "w", ZIP_DEFLATED) as archive:
            for path, name in members:
                archive.write(path, name)
        verify_release_archive(partial)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="archive a built release directory and verify it")
    create.add_argument("source", type=Path)
    create.add_argument("destination", type=Path)
    verify = commands.add_parser("verify", help="check existing archives with the updater's staging rules")
    verify.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            print(f"Created verified release archive: {create_release_archive(args.source, args.destination)}")
        else:
            for archive in args.archives:
                print(f"Verified release archive ({len(verify_release_archive(archive))} entries): {archive}")
    except (OSError, ValueError, BadZipFile, LargeZipFile) as error:
        print(f"Release archive check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
