"""Repository item scanner composed from path and content rules."""

from typing import TYPE_CHECKING

from src.tools.public_safety.content_rules import content_findings
from src.tools.public_safety.models import Finding, deduplicate
from src.tools.public_safety.path_rules import normalize_path, path_findings

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def scan_items(items: Mapping[str, bytes], deny_terms: Sequence[str] = ()) -> list[Finding]:
    findings: list[Finding] = []
    for original_path, payload in sorted(items.items()):
        path = normalize_path(original_path)
        current_path_findings = path_findings(path, len(payload))
        if path == ".env" and payload.strip() == b"PYTHONPATH=./src":
            current_path_findings = [
                finding for finding in current_path_findings if finding.rule != "sensitive-filename"
            ]
        findings.extend(current_path_findings)
        findings.extend(content_findings(path, payload, deny_terms))
    return deduplicate(findings)
