from src.tools.public_safety.scanner import scan_items


def test_scan_combines_path_content_and_local_denylist_rules() -> None:
    private_marker = "private-handle"
    token = "github_pat_" + "x" * 40
    items = {"captures/session.jsonl": b"{}\n", "notes.txt": f"{private_marker}\n{token}\n".encode()}

    findings = scan_items(items, (private_marker,))
    rules = {finding.rule for finding in findings}

    assert {"private-data-directory", "sensitive-file-type", "local-denylist", "github-token"} <= rules
    assert all(private_marker not in finding.detail for finding in findings)
    assert all(token not in finding.detail for finding in findings)


def test_scan_normalizes_and_deduplicates_findings() -> None:
    findings = scan_items({r".\captures\session.jsonl": b"{}"})

    assert all(finding.path == "captures/session.jsonl" for finding in findings)
    assert len({(finding.rule, finding.path, finding.line, finding.detail) for finding in findings}) == len(findings)


def test_scan_allows_only_the_known_public_root_environment_file() -> None:
    assert not scan_items({".env": b"PYTHONPATH=./src\n"})
    assert "sensitive-filename" in {finding.rule for finding in scan_items({".env": b"DEBUG=true\n"})}
