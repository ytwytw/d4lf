"""Read complete staged or committed file snapshots from Git objects."""

import io
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class GitSourceError(RuntimeError):
    pass


def _run_git(arguments: Sequence[str], *, cwd: Path | None = None, stdin: bytes | None = None) -> bytes:
    process = subprocess.run(["git", *arguments], cwd=cwd, input=stdin, check=False, capture_output=True)
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        command = " ".join(arguments)
        message = f"git {command} failed: {detail}"
        raise GitSourceError(message)
    return process.stdout


def git_root(cwd: Path | None = None) -> Path:
    return Path(_run_git(["rev-parse", "--show-toplevel"], cwd=cwd).decode("utf-8").strip())


def _read_blobs(entries: list[tuple[bytes, str]], *, cwd: Path) -> dict[str, bytes]:
    if not entries:
        return {}
    queries = b"".join(object_id + b"\n" for object_id, _path in entries)
    raw_output = _run_git(["cat-file", "--batch"], cwd=cwd, stdin=queries)
    output = io.BytesIO(raw_output)
    items: dict[str, bytes] = {}

    for expected_id, path in entries:
        header = output.readline().rstrip(b"\n").split()
        if len(header) != 3 or header[0] != expected_id:
            message = "git cat-file returned an unexpected object header"
            raise GitSourceError(message)
        try:
            size = int(header[2])
        except ValueError as error:
            message = "git cat-file returned an invalid object size"
            raise GitSourceError(message) from error
        payload = output.read(size)
        if len(payload) != size or output.read(1) != b"\n":
            message = "git cat-file returned a truncated object"
            raise GitSourceError(message)
        if path in items:
            items[path] += b"\n" + payload
        else:
            items[path] = payload
    return items


def tree_items(revision: str, *, cwd: Path | None = None) -> dict[str, bytes]:
    root = git_root(cwd)
    raw_entries = _run_git(["ls-tree", "-r", "-z", "--full-tree", revision], cwd=root)
    entries: list[tuple[bytes, str]] = []
    for raw_entry in raw_entries.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", maxsplit=1)
        _mode, object_type, object_id = metadata.split(maxsplit=2)
        if object_type == b"blob":
            entries.append((object_id, raw_path.decode("utf-8", errors="surrogateescape")))
    return _read_blobs(entries, cwd=root)


def index_items(*, cwd: Path | None = None) -> dict[str, bytes]:
    root = git_root(cwd)
    raw_entries = _run_git(["ls-files", "--stage", "-z"], cwd=root)
    entries: list[tuple[bytes, str]] = []
    for raw_entry in raw_entries.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", maxsplit=1)
        mode, object_id, _stage = metadata.split(maxsplit=2)
        if mode != b"160000":
            entries.append((object_id, raw_path.decode("utf-8", errors="surrogateescape")))
    return _read_blobs(entries, cwd=root)
