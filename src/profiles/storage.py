"""Crash-safe profile file writes and re-import comparison."""

import os
import re
import tempfile
import time
from pathlib import Path

_REPLACE_ATTEMPTS = 5
_IMPORTED_AT = re.compile(r"^(\s*imported_at:).*$", re.MULTILINE)


def atomic_write_text(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` via a synced sibling file; the old content survives any failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        _replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _replace(source: Path, target: Path) -> None:
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            source.replace(target)
        except PermissionError:
            # Windows refuses the swap while another reader briefly holds the old file open.
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
        else:
            return


def import_body(text: str) -> str:
    """Profile YAML without the generated header comments or the per-run import timestamp."""
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return _IMPORTED_AT.sub(r"\1", "\n".join(lines)).strip()


def matches_import(path: Path, body: str) -> bool:
    """Whether an existing file holds exactly this import, so refreshing it cannot lose user edits."""
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError, UnicodeError:
        return False
    return import_body(existing) == import_body(body)


__all__ = ["atomic_write_text", "import_body", "matches_import"]
