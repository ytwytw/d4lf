import json
from typing import TYPE_CHECKING

import pytest

from src.tools import release_check
from src.tools.release_acceptance import ACCEPTANCE_PATH
from src.tools.release_check import check_release_readiness, evaluate_release_readiness

if TYPE_CHECKING:
    from pathlib import Path

GAP = "gap A"
KEYS = [
    "manifest.json:runtime_ready",
    f"manifest.json:readiness_blocker:{GAP}",
    "quality-report.json:runtime_ready",
    f"quality-report.json:readiness_blocker:{GAP}",
]


def _reports(root: Path, blockers=(GAP,), **quality) -> None:
    directory = root / "assets/lang/zhCN"
    directory.mkdir(parents=True, exist_ok=True)
    base = {"runtime_ready": False, "readiness_blockers": list(blockers)}
    (directory / "manifest.json").write_text(json.dumps({**base, "source_quality_ok": True}), encoding="utf-8")
    payload = {**base, "summary": {"source_quality_ok": True}, **quality}
    (directory / "quality-report.json").write_text(json.dumps(payload), encoding="utf-8")


def _entry(failures=tuple(KEYS), **overrides) -> dict[str, object]:
    return {
        "id": "known-gap",
        "limitation": "Unidentified text is skipped.",
        "live_validated": False,
        "failures": list(failures),
        "runtime_guard": ["tests/guard_test.py::test_guard[case]"],
        **overrides,
    }


def _ledger(root: Path, *entries: dict[str, object], **overrides) -> None:
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests/guard_test.py").write_text("def test_guard():\n    pass\n", encoding="utf-8")
    data = {"schema_version": 1, "locale": "zhCN", "basis": "Fail-closed runtime.", "accepted": list(entries)}
    (root / ACCEPTANCE_PATH).write_text(json.dumps({**data, **overrides}, ensure_ascii=False), encoding="utf-8")


def test_exact_match_accepts_documented_limitations(tmp_path) -> None:
    _reports(tmp_path)
    _ledger(tmp_path, _entry())
    result = evaluate_release_readiness(tmp_path)
    assert result.blocking == ()
    assert [entry.id for entry in result.accepted] == ["known-gap"]


def test_missing_ledger_blocks_every_locale_failure(tmp_path) -> None:
    _reports(tmp_path)
    assert len(check_release_readiness(tmp_path)) == len(KEYS)


def test_new_failure_blocks(tmp_path) -> None:
    _reports(tmp_path, blockers=(GAP, "gap B"))
    _ledger(tmp_path, _entry())
    assert check_release_readiness(tmp_path) == [
        "manifest.json: unresolved readiness_blocker: gap B",
        "quality-report.json: unresolved readiness_blocker: gap B",
    ]


def test_stale_acceptance_blocks(tmp_path) -> None:
    _reports(tmp_path, blockers=())
    _ledger(tmp_path, _entry())
    blocking = check_release_readiness(tmp_path)
    assert blocking == [
        f"release-acceptance.json: stale acceptance for a failure that no longer occurs: {key}"
        for key in sorted(KEYS[1::2])
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"unresolved": [{"stable_id": "affixes:new"}]},
        {"summary": {"source_quality_ok": True, "source_builds_match": False}, "source_builds": {"d2core": "1"}},
        {"companion_quality": {"ok": False, "summary": {"missing_locale_records": 2}}},
        {"selected_quality": {"alias_collisions": [{"namespace": "tributes", "normalized_alias": "新"}]}},
        {"translation_conflicts": [{"stable_id": "x"}]},
    ],
)
def test_new_quality_reason_is_a_new_failure(tmp_path, change) -> None:
    _reports(tmp_path, **change)
    _ledger(tmp_path, _entry())
    blocking = check_release_readiness(tmp_path)
    assert len(blocking) == 1
    assert blocking[0].startswith("quality-report.json: ")


@pytest.mark.parametrize(
    "ledger",
    [
        {"entries": [_entry(live_validated=True)]},
        {"entries": [{key: value for key, value in _entry().items() if key != "live_validated"}]},
        {"entries": [_entry(extra="field")]},
        {"entries": [_entry(failures=[])]},
        {"entries": [_entry(limitation=" ")]},
        {"entries": [_entry(runtime_guard=[])]},
        {"entries": [_entry(runtime_guard=["tests/missing_test.py::test_guard"])]},
        {"entries": [_entry(runtime_guard=["tests/guard_test.py::test_absent"])]},
        {"entries": [_entry(runtime_guard=["guard_test.py"])]},
        {"entries": [_entry(failures=KEYS[:2]), _entry(id="other", failures=KEYS[1:])]},
        {"entries": [_entry()], "overrides": {"schema_version": 2}},
        {"entries": [_entry()], "overrides": {"basis": ""}},
        {"entries": [_entry()], "overrides": {"note": "unexpected"}},
    ],
)
def test_malformed_ledger_waives_nothing(tmp_path, ledger) -> None:
    _reports(tmp_path)
    _ledger(tmp_path, *ledger["entries"], **ledger.get("overrides", {}))
    blocking = check_release_readiness(tmp_path)
    assert any(message.startswith("release-acceptance.json:") for message in blocking)
    assert "manifest.json: runtime_ready is not true" in blocking


@pytest.mark.parametrize("text", ["{", "[]", "null"])
def test_unreadable_ledger_waives_nothing(tmp_path, text) -> None:
    _reports(tmp_path)
    _ledger(tmp_path, _entry())
    (tmp_path / ACCEPTANCE_PATH).write_text(text, encoding="utf-8")
    assert len(check_release_readiness(tmp_path)) == len(KEYS) + 1


def test_bundled_source_and_unreadable_report_failures_can_never_be_accepted(tmp_path) -> None:
    _reports(tmp_path)
    directory = tmp_path / "assets/equipment_knowledge"
    directory.mkdir(parents=True)
    source = {"provider": "D2Core", "file": "items.json", "public_redistribution": "unverified"}
    (directory / "catalog-1.json").write_text(json.dumps({"sources": [source]}), encoding="utf-8")
    bundled = "bundled:catalog-1.json: D2Core / items.json"
    _ledger(tmp_path, _entry(failures=[*KEYS, bundled]))
    assert check_release_readiness(tmp_path) == [
        "catalog-1.json: D2Core / items.json: public redistribution is not verified",
        f"release-acceptance.json: {bundled} can never be accepted",
    ]
    (tmp_path / "assets/lang/zhCN/manifest.json").write_text("null", encoding="utf-8")
    assert "manifest.json: readiness report must be an object" in check_release_readiness(tmp_path)


def test_main_reports_accepted_limitations_for_the_repository(capsys) -> None:
    assert release_check.main() == 0
    output = capsys.readouterr().out
    assert "accepted known limitations (live_validated=false)" in output
    assert "shared-tribute-label-heritage-titans" in output
