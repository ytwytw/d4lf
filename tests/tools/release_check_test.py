import json
from pathlib import Path

import pytest

from src.tools.release_check import check_release_readiness


def _reports(root, **overrides):
    directory = root / "assets/lang/zhCN"
    directory.mkdir(parents=True)
    report = {"runtime_ready": True, "source_quality_ok": True, "readiness_blockers": [], **overrides}
    for name in ("manifest.json", "quality-report.json"):
        payload = report.copy()
        if name == "quality-report.json":
            payload["summary"] = {"source_quality_ok": payload.pop("source_quality_ok")}
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_complete_locale_allows_publication(tmp_path) -> None:
    _reports(tmp_path)
    assert not check_release_readiness(tmp_path)


@pytest.mark.parametrize(
    "flags",
    [
        {"runtime_ready": False},
        {"source_quality_ok": False},
        {"runtime_ready": "true"},
        {"readiness_blockers": ["missing translations"]},
    ],
)
def test_partial_locale_blocks_publication(tmp_path, flags) -> None:
    _reports(tmp_path, **flags)
    assert check_release_readiness(tmp_path)


def test_missing_reports_block_publication(tmp_path) -> None:
    assert len(check_release_readiness(tmp_path)) == 2


def test_malformed_report_blocks_publication(tmp_path) -> None:
    _reports(tmp_path)
    (tmp_path / "assets/lang/zhCN/quality-report.json").write_text("null", encoding="utf-8")
    assert check_release_readiness(tmp_path) == ["quality-report.json: readiness report must be an object"]


def test_actual_audit_schema_matches_publication_gate() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "assets/lang/zhCN/manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((root / "assets/lang/zhCN/quality-report.json").read_text(encoding="utf-8"))
    failures = check_release_readiness(root)
    expected_ready = (
        manifest["runtime_ready"] is True
        and manifest["source_quality_ok"] is True
        and not manifest.get("readiness_blockers")
        and quality["runtime_ready"] is True
        and quality["summary"]["source_quality_ok"] is True
        and not quality.get("readiness_blockers")
    )
    assert (not failures) == expected_ready
