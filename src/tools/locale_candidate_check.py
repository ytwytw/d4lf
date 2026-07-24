from __future__ import annotations

# Structured validation messages are intentionally kept at their call sites.
# ruff: noqa: EM102
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.tools import locale_data_check

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INPUT_ERROR = 2


class CandidateInputError(ValueError):
    pass


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CandidateInputError(f"{label} does not exist: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateInputError(f"{label} is not valid UTF-8 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateInputError(f"{label} must contain a JSON object: {path}")
    return cast("dict[str, object]", value)


def _stable_ids(values: object, label: str) -> set[str]:
    if not isinstance(values, list):
        raise CandidateInputError(f"{label} must be an array")
    result: set[str] = set()
    for index, value in enumerate(values):
        stable_id = value.get("stable_id") if isinstance(value, dict) else None
        if not isinstance(stable_id, str):
            raise CandidateInputError(f"{label}[{index}].stable_id must be a string")
        if stable_id in result:
            raise CandidateInputError(f"{label} contains duplicate stable ID {stable_id!r}")
        result.add(stable_id)
    return result


def _report(status: str, issues: list[dict[str, object]], base_report: Mapping[str, object]) -> dict[str, object]:
    issue_counts: Counter[str] = Counter()
    for issue in issues:
        code = issue.get("code")
        if isinstance(code, str):
            issue_counts[code] += 1
    return {
        "ok": not issues,
        "status": status if not issues else "failed",
        "exit_code": EXIT_OK if not issues else EXIT_FAILED,
        "summary": {"issues": len(issues), "issue_counts": dict(sorted(issue_counts.items()))},
        "issues": issues,
        "release_gate": base_report,
    }


def check_candidate(
    *, source_lock: Path, build_version: Path, locale_manifest: Path, quality_report: Path
) -> dict[str, object]:
    base_report = locale_data_check.check_locale_data(
        source_lock=source_lock, build_version=build_version, locale_manifest=locale_manifest
    )
    try:
        quality = _load_json_object(quality_report, "quality report")
        locale = _load_json_object(locale_manifest, "locale manifest")
        unresolved_ids = _stable_ids(quality.get("unresolved"), "quality_report.unresolved")
    except CandidateInputError as error:
        return {
            "ok": False,
            "status": "input_error",
            "exit_code": EXIT_INPUT_ERROR,
            "summary": {"issues": 1, "issue_counts": {"invalid_input": 1}},
            "issues": [{"code": "invalid_input", "message": str(error)}],
            "release_gate": base_report,
        }

    issues: list[dict[str, object]] = [
        {
            "code": "metadata_mismatch",
            "message": f"quality report and locale manifest disagree on {field}",
            "field": field,
        }
        for field in ("schema_version", "build_version", "locale", "runtime_ready")
        if quality.get(field) != locale.get(field)
    ]

    summary = quality.get("summary")
    conflict_count = summary.get("translation_conflicts") if isinstance(summary, dict) else None
    source_builds_match = summary.get("source_builds_match") if isinstance(summary, dict) else None
    source_quality_ok = summary.get("source_quality_ok") if isinstance(summary, dict) else None
    if locale.get("translation_conflicts") != conflict_count:
        issues.append({
            "code": "metadata_mismatch",
            "message": "quality report and locale manifest disagree on translation_conflicts",
            "field": "translation_conflicts",
        })
    if locale.get("source_quality_ok") != source_quality_ok:
        issues.append({
            "code": "metadata_mismatch",
            "message": "quality report and locale manifest disagree on source_quality_ok",
            "field": "source_quality_ok",
        })

    base_issues = base_report.get("issues", [])
    if not isinstance(base_issues, list):
        base_issues = []
    missing_ids: set[str] = set()
    for raw_issue in base_issues:
        if not isinstance(raw_issue, dict):
            continue
        issue = cast("dict[str, object]", raw_issue)
        stable_id = issue.get("stable_id")
        if issue.get("code") == "missing_record" and isinstance(stable_id, str):
            missing_ids.add(stable_id)
    runtime_ready = quality.get("runtime_ready") is True
    expected_blocking_codes: set[str] = set()
    if not runtime_ready:
        expected_blocking_codes.add("runtime_not_ready")
    if source_builds_match is False:
        expected_blocking_codes.add("provider_build_mismatch")
    if source_quality_ok is False:
        expected_blocking_codes.add("source_quality_failed")
    if type(conflict_count) is int and conflict_count > 0:
        expected_blocking_codes.add("translation_conflict")

    base_issue_codes: set[str] = set()
    for raw_issue in base_issues:
        code = raw_issue.get("code") if isinstance(raw_issue, dict) else None
        if isinstance(code, str):
            base_issue_codes.add(code)
    unexpected_release_issues = [
        issue
        for issue in base_issues
        if not isinstance(issue, dict) or issue.get("code") not in {"missing_record", *expected_blocking_codes}
    ]
    if unexpected_release_issues:
        issues.append({
            "code": "release_gate_error",
            "message": "release gate contains findings other than declared missing records",
            "count": len(unexpected_release_issues),
        })
    missing_blockers = expected_blocking_codes - base_issue_codes
    if missing_blockers:
        issues.append({
            "code": "release_gate_error",
            "message": "release gate is missing declared candidate blockers",
            "missing_codes": sorted(missing_blockers),
        })
    if missing_ids != unresolved_ids:
        issues.append({
            "code": "unresolved_mismatch",
            "message": "release-gate missing IDs do not match the declared unresolved IDs",
            "missing_from_quality": sorted(missing_ids - unresolved_ids),
            "missing_from_release_gate": sorted(unresolved_ids - missing_ids),
        })

    if not isinstance(summary, dict) or summary.get("unresolved_records") != len(unresolved_ids):
        issues.append({
            "code": "summary_mismatch",
            "message": "quality summary unresolved count does not match unresolved records",
        })

    if runtime_ready and (unresolved_ids or base_report.get("exit_code") != locale_data_check.EXIT_OK):
        issues.append({"code": "false_ready", "message": "runtime_ready is true while the release gate is not clean"})
    has_declared_blocker = bool(
        unresolved_ids
        or source_builds_match is False
        or source_quality_ok is False
        or (type(conflict_count) is int and conflict_count > 0)
    )
    if not runtime_ready and not has_declared_blocker:
        issues.append({"code": "false_candidate", "message": "runtime_ready is false without a declared blocker"})

    return _report("ready" if runtime_ready else "candidate", issues, base_report)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate that a declared locale candidate fails closed coherently.")
    parser.add_argument("--source-lock", required=True, type=Path)
    parser.add_argument("--build-version", required=True, type=Path)
    parser.add_argument("--locale-manifest", required=True, type=Path)
    parser.add_argument("--quality-report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    report = check_candidate(
        source_lock=arguments.source_lock,
        build_version=arguments.build_version,
        locale_manifest=arguments.locale_manifest,
        quality_report=arguments.quality_report,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return cast("int", report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
