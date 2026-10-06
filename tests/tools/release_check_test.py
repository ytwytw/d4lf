import json
from pathlib import Path

import pytest

from src.tools.release_acceptance import ACCEPTANCE_PATH, load_ledger
from src.tools.release_check import check_release_readiness, collect_readiness_failures, evaluate_release_readiness


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


def _catalog(root: Path, sources) -> None:
    directory = root / "assets/equipment_knowledge"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "catalog-12345.json").write_text(json.dumps({"sources": sources}), encoding="utf-8")


@pytest.mark.parametrize("status", ["unverified", "private", None, True])
def test_ready_locale_does_not_override_bundled_private_data(tmp_path, status) -> None:
    _reports(tmp_path)
    _catalog(tmp_path, [{"provider": "D2Core", "file": "items.json", "public_redistribution": status}])
    assert check_release_readiness(tmp_path) == [
        "catalog-12345.json: D2Core / items.json: public redistribution is not verified"
    ]


def test_verified_marker_requires_recorded_evidence(tmp_path) -> None:
    _reports(tmp_path)
    source = {"provider": "D2Core", "file": "items.json", "public_redistribution": "verified"}
    _catalog(tmp_path, [source])
    assert check_release_readiness(tmp_path) == [
        "catalog-12345.json: D2Core / items.json: public redistribution evidence is missing"
    ]
    _catalog(tmp_path, [{**source, "public_redistribution_evidence": "Documented permission for this snapshot"}])
    assert not check_release_readiness(tmp_path)


@pytest.mark.parametrize("sources", [None, [], [None]])
def test_bundled_catalog_without_readable_provenance_blocks_publication(tmp_path, sources) -> None:
    _reports(tmp_path)
    _catalog(tmp_path, sources)
    assert check_release_readiness(tmp_path)


def test_unbundled_research_catalog_does_not_block_publication(tmp_path) -> None:
    _reports(tmp_path)
    _catalog(tmp_path / ".scratch", [{"provider": "D2Core", "public_redistribution": "unverified"}])
    assert not check_release_readiness(tmp_path)


def test_other_bundled_sources_keep_existing_license_workflow(tmp_path) -> None:
    _reports(tmp_path)
    _catalog(tmp_path, [{"provider": "Community compilation", "license": "MIT"}])
    assert not check_release_readiness(tmp_path)


def test_shards_use_index_provenance_and_cannot_replace_a_missing_index(tmp_path) -> None:
    _reports(tmp_path)
    _catalog(tmp_path, [{"provider": "Community compilation", "license": "MIT"}])
    directory = tmp_path / "assets/equipment_knowledge"
    (directory / "catalog-12345-items-01.json").write_text('{"items": []}', encoding="utf-8")
    assert not check_release_readiness(tmp_path)
    (directory / "catalog-12345.json").unlink()
    assert check_release_readiness(tmp_path) == ["equipment_knowledge: missing bundled catalog provenance"]


def test_actual_audit_schema_matches_publication_gate() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "assets/lang/zhCN/manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((root / "assets/lang/zhCN/quality-report.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "assets/equipment_knowledge/catalog-73552.json").read_text(encoding="utf-8"))
    failures = collect_readiness_failures(root)
    expected_ready = (
        manifest["runtime_ready"] is True
        and manifest["source_quality_ok"] is True
        and not manifest.get("readiness_blockers")
        and quality["runtime_ready"] is True
        and quality["summary"]["source_quality_ok"] is True
        and not quality.get("readiness_blockers")
        and all(
            source.get("public_redistribution") == "verified" and source.get("public_redistribution_evidence")
            for source in catalog["sources"]
            if source.get("provider") == "D2Core" or "public_redistribution" in source
        )
    )
    assert (not failures) == expected_ready
    # The ledger never rewrites the generator's factual flags.
    assert manifest["runtime_ready"] is quality["runtime_ready"] is False
    assert manifest["source_quality_ok"] is quality["summary"]["source_quality_ok"] is False


def test_repository_policy_accepts_exactly_the_current_locale_failures() -> None:
    root = Path(__file__).resolve().parents[2]
    failures = collect_readiness_failures(root)
    entries, errors = load_ledger(root)
    assert not errors
    assert all(failure.waivable for failure in failures)
    assert {key for entry in entries for key in entry.failures} == {failure.key for failure in failures}
    assert check_release_readiness(root) == []
    result = evaluate_release_readiness(root)
    assert [entry.id for entry in result.accepted] == [entry.id for entry in entries]
    raw = json.loads((root / ACCEPTANCE_PATH).read_text(encoding="utf-8"))
    assert all(entry["live_validated"] is False for entry in raw["accepted"])
    tribute = next(entry for entry in entries if "巨人贡品" in entry.limitation)
    assert any(node.startswith("tests/profiles/editor/identity_test.py::") for node in tribute.runtime_guard)
