"""Command-line entry point for seasonal locale-data monitoring."""

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.tools.season_data_watch.manifest import WatchInputError
from src.tools.season_data_watch.watch import EXIT_INPUT_ERROR, check_sources

if TYPE_CHECKING:
    from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check locked locale inputs for upstream seasonal data drift.")
    parser.add_argument("--source-lock", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = check_sources(arguments.source_lock)
    except (WatchInputError, ValueError) as error:
        report = {
            "ok": False,
            "status": "input_error",
            "exit_code": EXIT_INPUT_ERROR,
            "issues": [{"code": "input_error", "message": str(error)}],
        }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return cast("int", report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
