"""High-confidence private-data and credential content rules."""

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from src.tools.public_safety.models import Finding

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class _ContentRule:
    name: str
    pattern: re.Pattern[str]
    detail: str
    scan_binary: bool = True


_RULES = (
    _ContentRule(
        "private-key",
        re.compile(r"-{5}BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-{5}", re.IGNORECASE),
        "remove the private key from Git and rotate it if it is real",
    ),
    _ContentRule(
        "github-token",
        re.compile(r"\b(?:gh[opsu]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"),
        "remove the GitHub token from Git and revoke or rotate it if it is real",
    ),
    _ContentRule(
        "openai-token",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
        "remove the API token from Git and rotate it if it is real",
    ),
    _ContentRule(
        "aws-access-key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "remove the cloud access key from Git and rotate it if it is real",
    ),
    _ContentRule(
        "google-api-key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "remove the API key from Git and rotate it if it is real",
    ),
    _ContentRule(
        "slack-token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"),
        "remove the service token from Git and rotate it if it is real",
    ),
    _ContentRule(
        "stripe-live-key",
        re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
        "remove the live payment key from Git and rotate it if it is real",
    ),
    _ContentRule(
        "discord-webhook",
        re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9._-]+", re.IGNORECASE),
        "remove the webhook URL from Git and rotate it if it is real",
    ),
    _ContentRule(
        "bearer-token",
        re.compile(r"\b(?:authorization\s*[:=]\s*)?bearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE),
        "remove the bearer token from Git and rotate it if it is real",
    ),
    _ContentRule(
        "url-credentials",
        re.compile(r"https?://[^/\s:@]+:[^/\s@]{4,}@", re.IGNORECASE),
        "remove credentials embedded in the URL and rotate them if they are real",
    ),
    _ContentRule(
        "credential-assignment",
        re.compile(
            r"\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|password|passwd|private[_-]?key)"
            r"\b\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{16,}",
            re.IGNORECASE,
        ),
        "replace the credential value with an environment/secret reference and rotate it if real",
        scan_binary=False,
    ),
    _ContentRule(
        "windows-home-path",
        re.compile(
            r"(?:[A-Z]:|\\\\[^\\/\s]+)[\\/]Users[\\/]+"
            r"(?!(?:Public|you|user|username|yourname)(?:[\\/]|$))"
            r"(?![\[<${%])[^\\/\s\"'<>]+",
            re.IGNORECASE,
        ),
        "replace the personal Windows profile path with a repository-relative or placeholder path",
    ),
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,}|invalid)\b", re.IGNORECASE)
_ALLOWED_EMAIL_DOMAINS = {"example.com", "example.net", "example.org", "invalid", "users.noreply.github.com"}
_CAPTURE_DIGEST_FIELD = '"input_' + 'sha256"'


def _email_allowed(match: re.Match[str]) -> bool:
    domain = match.group(1).casefold()
    return domain in _ALLOWED_EMAIL_DOMAINS or domain.endswith(".invalid")


def _denylist_findings(path: str, payload: bytes, text: str | None, deny_terms: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    folded_lines = [line.casefold() for line in text.splitlines()] if text is not None else []
    for index, term in enumerate(deny_terms, start=1):
        matched_text = False
        for line_number, line in enumerate(folded_lines, start=1):
            if term.casefold() in line:
                matched_text = True
                findings.append(
                    Finding(
                        "local-denylist", path, f"remove content matching private denylist entry {index}", line_number
                    )
                )
        if matched_text:
            continue
        variants = {term, term.casefold(), term.upper()}
        encoded_terms = {
            variant.encode(encoding, errors="ignore")
            for variant in variants
            for encoding in ("utf-8", "utf-16-le", "utf-16-be")
        }
        if any(encoded and encoded in payload for encoded in encoded_terms):
            findings.append(
                Finding("local-denylist", path, f"remove binary metadata matching private denylist entry {index}")
            )
    return findings


def _structured_capture_findings(path: str, text: str) -> list[Finding]:
    if PurePosixPath(path).suffix.casefold() != ".json":
        return []
    try:
        structured = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(structured, dict):
        return []

    findings: list[Finding] = []
    input_metadata = structured.get("input")
    if isinstance(input_metadata, dict) and isinstance(input_metadata.get("sha256"), str):
        findings.append(
            Finding("capture-fingerprint", path, "remove the private replay input digest and capture report from Git")
        )
    tts_metadata = structured.get("tts")
    if (
        isinstance(structured.get("fingerprint"), str)
        and isinstance(tts_metadata, dict)
        and ("raw_lines" in tts_metadata or "framed_lines" in tts_metadata)
    ):
        findings.append(Finding("capture-artifact", path, "remove the automatic failure-capture manifest from Git"))
    return findings


def content_findings(path: str, payload: bytes, deny_terms: Sequence[str] = ()) -> list[Finding]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = None

    findings = _denylist_findings(path, payload, text, deny_terms)
    if text is None:
        binary_text = payload.decode("latin-1", errors="ignore")
        for rule in _RULES:
            if rule.scan_binary and rule.pattern.search(binary_text):
                findings.append(Finding(rule.name, path, rule.detail))
        return findings

    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in _RULES:
            if rule.pattern.search(line):
                findings.append(Finding(rule.name, path, rule.detail, line_number))
        for match in _EMAIL_PATTERN.finditer(line):
            if not _email_allowed(match):
                findings.append(
                    Finding(
                        "email-address",
                        path,
                        "replace the real email with a GitHub noreply or placeholder address",
                        line_number,
                    )
                )
        if _CAPTURE_DIGEST_FIELD in line.casefold():
            findings.append(
                Finding(
                    "capture-fingerprint",
                    path,
                    "remove the private replay input digest and capture report from Git",
                    line_number,
                )
            )
    findings.extend(_structured_capture_findings(path, text))
    return findings
