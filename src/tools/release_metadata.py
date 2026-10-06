"""Describe the current release and render its user-facing notes with absolute GitHub links."""

import argparse
import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import quote

from src import __version__
from src.release_versions import is_prerelease, version_key
from src.tools.release_archive import archive_name

ROOT = Path(__file__).resolve().parents[2]
NOTES_PATH = ROOT / "docs" / "release-notes.zh-CN.md"
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
_LINK_RE = re.compile(r"(?P<image>!?)\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)\)")
_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def release_metadata(version: str = __version__) -> dict[str, str]:
    """Validate the version with the updater's ordering rules so a published tag is always discoverable."""
    if version_key(version) is None:
        msg = f"Version cannot be ordered by the updater: {version!r}"
        raise ValueError(msg)
    return {
        "version": version,
        "tag": f"v{version}",
        "prerelease": "true" if is_prerelease(version) else "false",
        "zip_name": archive_name(version),
    }


def _absolute_link(match: re.Match[str], *, document: str, repository: str, ref: str, root: Path) -> str:
    target = match["target"]
    if _SCHEME_RE.match(target):
        return match[0]
    path, _, fragment = target.partition("#")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(document), path)) if path else document
    if resolved.startswith("../") or not (root / resolved).is_file():
        msg = f"Release notes link does not point to a repository file: {target}"
        raise ValueError(msg)
    kind = "raw" if match["image"] else "blob"
    url = f"https://github.com/{repository}/{kind}/{quote(ref, safe='')}/{quote(resolved)}"
    return f"{match['image']}[{match['text']}]({url}{'#' + fragment if fragment else ''})"


def render_release_body(repository: str, ref: str, source: Path = NOTES_PATH, root: Path = ROOT) -> str:
    """Drop the document title (the release has its own) and make every repository link absolute."""
    if not _REPOSITORY_RE.fullmatch(repository):
        msg = f"Invalid GitHub repository: {repository!r}"
        raise ValueError(msg)
    lines = source.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = "\n".join(lines).strip() + "\n"
    document = source.resolve().relative_to(root.resolve()).as_posix()
    return _LINK_RE.sub(
        lambda match: _absolute_link(match, document=document, repository=repository, ref=ref, root=root), body
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="print the validated application version")
    output = commands.add_parser("github-output", help="append version, tag, prerelease and zip_name")
    output.add_argument("path", type=Path)
    notes = commands.add_parser("notes", help="write the user-facing release body")
    notes.add_argument("--repository", required=True)
    notes.add_argument("--ref", required=True, help="tag or commit used for absolute links")
    notes.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print(release_metadata()["version"])
        elif args.command == "github-output":
            with args.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.writelines(f"{key}={value}\n" for key, value in release_metadata().items())
        else:
            args.output.write_text(render_release_body(args.repository, args.ref), encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        print(f"Release metadata check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
