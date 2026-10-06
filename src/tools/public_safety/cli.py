"""CLI orchestration and redacted output for the public safety gate."""

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.tools.public_safety.git_source import GitSourceError, git_root, index_items, tree_items
from src.tools.public_safety.scanner import scan_items

if TYPE_CHECKING:
    from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reject private captures, identity traces, credentials, and generated reports before publication."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--index", action="store_true", help="scan the complete staged Git index")
    source.add_argument("--tree", metavar="REV", help="scan a committed Git tree such as HEAD")
    parser.add_argument(
        "--denylist", type=Path, help="optional local literal denylist; matched values are never printed"
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def _load_deny_terms(path: Path | None) -> tuple[str, ...]:
    if path is None or not path.exists():
        return ()
    terms = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            terms.append(stripped)
    return tuple(terms)


def _default_denylist(root: Path, configured: Path | None) -> Path | None:
    if configured is not None:
        return configured
    candidate = root / ".public-safety.local"
    return candidate if candidate.exists() else None


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        root = git_root()
        deny_terms = _load_deny_terms(_default_denylist(root, arguments.denylist))
        items = index_items(cwd=root) if arguments.index else tree_items(arguments.tree, cwd=root)
        findings = scan_items(items, deny_terms)
    except (GitSourceError, OSError, UnicodeError) as error:
        print(f"Public safety scan could not run: {error}", file=sys.stderr)
        return 2

    if findings:
        print(f"Public safety scan failed with {len(findings)} finding(s):", file=sys.stderr)
        for finding in findings[:200]:
            location = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path
            print(f"- [{finding.rule}] {location}: {finding.detail}", file=sys.stderr)
        if len(findings) > 200:
            print(f"- {len(findings) - 200} additional finding(s) omitted", file=sys.stderr)
        return 1

    if not arguments.quiet:
        print(f"Public safety scan passed ({len(items)} files).")
    return 0
