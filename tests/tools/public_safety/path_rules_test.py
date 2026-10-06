from src.tools.public_safety.path_rules import MAX_TRACKED_FILE_BYTES, normalize_path, path_findings


def _rules(path: str, size: int = 1) -> set[str]:
    return {finding.rule for finding in path_findings(path, size)}


def test_normalizes_windows_paths() -> None:
    assert normalize_path(r".\captures\sample.jsonl") == "captures/sample.jsonl"


def test_rejects_private_artifact_paths_and_security_reports() -> None:
    assert "private-data-directory" in _rules("captures/session/manifest.json")
    assert "sensitive-file-type" in _rules("output/session.jsonl")
    assert "sensitive-file-type" in _rules("build/private.sqlite3")
    assert "capture-media" in _rules("tests/assets/screenshot_001.png")
    assert "scanner-report" in _rules("artifacts/gitleaks-report.json")
    assert "oversized-file" in _rules("large.bin", MAX_TRACKED_FILE_BYTES + 1)


def test_rejects_private_agent_files_but_allows_upstream_scaffolding() -> None:
    assert "sensitive-filename" in _rules("CLAUDE.md")
    assert "sensitive-filename" in _rules("nested/AGENTS.md")
    assert "private-data-directory" in _rules(".agents/zhcn-context.md")
    assert not _rules("AGENTS.md")
    assert not _rules("docs/agents/domain.md")
    assert not _rules("src/perception/capture/core.py")
    assert not _rules("tests/perception/capture/core_test.py")


def test_allows_public_fixtures_and_examples() -> None:
    assert not _rules("tests/assets/ui/tooltip.png")
    assert not _rules(".env.example")
