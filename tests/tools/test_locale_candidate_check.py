from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from src.tools import locale_candidate_check

REPO_ROOT = Path(__file__).resolve().parents[2]


def _committed_paths() -> dict[str, Path]:
    return {
        "source_lock": REPO_ROOT / "assets" / "catalog" / "source-lock.json",
        "build_version": REPO_ROOT / "assets" / "catalog" / "d4data-buildVersion.txt",
        "locale_manifest": REPO_ROOT / "assets" / "lang" / "zhCN" / "manifest.json",
        "quality_report": REPO_ROOT / "assets" / "lang" / "zhCN" / "quality-report.json",
    }


def test_committed_zhcn_candidate_is_internally_consistent_and_not_ready() -> None:
    report = locale_candidate_check.check_candidate(**_committed_paths())
    quality = json.loads(_committed_paths()["quality_report"].read_text(encoding="utf-8"))
    release_gate = report["release_gate"]
    assert isinstance(release_gate, dict)
    release_gate = cast("dict[str, object]", release_gate)
    summary = release_gate["summary"]
    assert isinstance(summary, dict)
    summary = cast("dict[str, object]", summary)

    assert report["exit_code"] == locale_candidate_check.EXIT_OK
    assert report["status"] == "candidate"
    assert report["issues"] == []
    assert release_gate["exit_code"] == 1
    issue_counts = cast("dict[str, int]", summary["issue_counts"])
    expected_issue_counts = {
        "missing_record": quality["summary"]["unresolved_records"],
        "provider_build_mismatch": 1,
        "runtime_not_ready": 1,
    }
    if quality["summary"]["translation_conflicts"]:
        expected_issue_counts["translation_conflict"] = 1
    if not quality["summary"]["source_quality_ok"]:
        expected_issue_counts["source_quality_failed"] = 1
    assert issue_counts == expected_issue_counts


def test_committed_zhcn_affixes_never_filter_nonempty_aggregated_translations() -> None:
    paths = _committed_paths()
    locale_dir = paths["locale_manifest"].parent
    affixes = json.loads((locale_dir / "affixes.json").read_text(encoding="utf-8"))
    manifest = json.loads(paths["locale_manifest"].read_text(encoding="utf-8"))
    quality = json.loads(paths["quality_report"].read_text(encoding="utf-8"))

    manifest_ids = {record["stable_id"] for record in manifest["records"] if record["stable_id"].startswith("affixes:")}
    nonempty_ids = {f"affixes:{canonical}" for canonical, display in affixes.items() if display.strip()}
    blank_ids = {f"affixes:{canonical}" for canonical, display in affixes.items() if not display.strip()}
    unresolved_ids = {
        record["stable_id"] for record in quality["unresolved"] if record["stable_id"].startswith("affixes:")
    }

    assert manifest_ids == nonempty_ids
    assert unresolved_ids == blank_ids
    assert quality["scope"]["excluded_historical_records"] == []
    assert quality["summary"]["excluded_historical_records"] == 0


def test_candidate_check_detects_tampered_unresolved_declaration(tmp_path: Path) -> None:
    paths = _committed_paths()
    quality = json.loads(paths["quality_report"].read_text(encoding="utf-8"))
    quality["unresolved"].pop()
    quality["summary"]["unresolved_records"] -= 1
    tampered_quality = tmp_path / "quality-report.json"
    tampered_quality.write_text(json.dumps(quality, ensure_ascii=False), encoding="utf-8")

    report = locale_candidate_check.check_candidate(**{**paths, "quality_report": tampered_quality})
    issues = report["issues"]
    assert isinstance(issues, list)
    assert all(isinstance(issue, dict) for issue in issues)
    typed_issues = cast("list[dict[str, object]]", issues)

    assert report["exit_code"] == locale_candidate_check.EXIT_FAILED
    assert any(issue["code"] == "unresolved_mismatch" for issue in typed_issues)


def test_candidate_check_rejects_provider_scope_exclusions(tmp_path: Path) -> None:
    paths = _committed_paths()
    quality = json.loads(paths["quality_report"].read_text(encoding="utf-8"))
    quality["scope"]["excluded_historical_records"] = [
        {
            "stable_id": "affixes:provider_absent",
            "reason": "absent_from_current_d2core",
            "translation_status": "translated",
        }
    ]
    quality["summary"]["excluded_historical_records"] = 1
    tampered_quality = tmp_path / "quality-report.json"
    tampered_quality.write_text(json.dumps(quality, ensure_ascii=False), encoding="utf-8")

    report = locale_candidate_check.check_candidate(**{**paths, "quality_report": tampered_quality})
    issues = cast("list[dict[str, object]]", report["issues"])

    assert report["exit_code"] == locale_candidate_check.EXIT_FAILED
    assert any(issue["code"] == "provider_scope_exclusion" for issue in issues)
