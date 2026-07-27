from src.tools.public_safety import Finding, scan_items


def test_public_facade_exports_scanner_and_finding() -> None:
    finding = Finding("rule", "path", "detail")

    assert finding.rule == "rule"
    assert scan_items({"README.md": b"public"}) == []
