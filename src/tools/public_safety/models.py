"""Shared result models for public repository safety checks."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    detail: str
    line: int | None = None


def deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    unique = {(finding.rule, finding.path, finding.line, finding.detail): finding for finding in findings}
    return sorted(unique.values(), key=lambda finding: (finding.path, finding.line or 0, finding.rule, finding.detail))
