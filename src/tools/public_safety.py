from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

MAX_TRACKED_FILE_BYTES = 25 * 1024 * 1024
PUBLIC_AUTHOR_NAME = "D4LF Public Release"
PUBLIC_AUTHOR_EMAIL = "public-release@invalid"
THIRD_PARTY_MANIFEST = "assets/catalog/source-manifest.json"
D2CORE_ATTRIBUTION_PATH = "README.md"
THIRD_PARTY_NOTICE_PATH = "THIRD-PARTY-NOTICES.md"
THIRD_PARTY_POLICY_PATH = "docs/third-party-data.md"
_MIT_DATA_SOURCES = {
    "d4data": (
        "DiabloTools/d4data",
        "https://github.com/DiabloTools/d4data.git",
        "https://github.com/DiabloTools/d4data",
        "Copyright (c) 2023 blizzhackers",
    ),
    "diablo4_companion": (
        "Diablo4Companion",
        "https://github.com/josdemmers/Diablo4Companion.git",
        "https://github.com/josdemmers/Diablo4Companion",
        "Copyright (c) 2022 Jos Demmers",
    ),
}

_FORBIDDEN_DIRECTORIES = {
    "audit-output",
    "capture",
    "captures",
    "crashdumps",
    "diagnostic-output",
    "diagnostics-output",
    "dumps",
    "obs",
    "private-data",
    "recordings",
    "screen-recordings",
    "screenshots",
}
_FORBIDDEN_FILENAMES = {
    ".env",
    ".npmrc",
    ".public-safety.local",
    ".pypirc",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "params.ini",
    "secrets.json",
    "verified_zhcn.json",
}
_FORBIDDEN_SUFFIXES = {
    ".7z",
    ".avi",
    ".bak",
    ".db",
    ".dmp",
    ".dump",
    ".exe",
    ".flac",
    ".gz",
    ".har",
    ".jsonl",
    ".kdbx",
    ".key",
    ".log",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".ndjson",
    ".p12",
    ".pcap",
    ".pcapng",
    ".pdb",
    ".pem",
    ".pfx",
    ".rar",
    ".sarif",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".wav",
    ".webm",
    ".zip",
}
_MEDIA_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png"}
_CAPTURE_FILE_PREFIXES = ("capture_", "dump_", "info_", "obs_", "screen_record", "screenshot")


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    detail: str
    line: int | None = None


@dataclass(frozen=True)
class _ContentRule:
    name: str
    pattern: re.Pattern[str]
    detail: str


_CONTENT_RULES = (
    _ContentRule(
        "private-key",
        re.compile(r"-{5}BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-{5}", re.IGNORECASE),
        "private key material is present",
    ),
    _ContentRule(
        "github-token",
        re.compile(r"\b(?:gh[opsu]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"),
        "a GitHub token-shaped value is present",
    ),
    _ContentRule(
        "openai-token", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"), "an API token-shaped value is present"
    ),
    _ContentRule(
        "aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "an AWS access key-shaped value is present"
    ),
    _ContentRule(
        "slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"), "a Slack token-shaped value is present"
    ),
    _ContentRule(
        "discord-webhook",
        re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9._-]+", re.IGNORECASE),
        "a Discord webhook URL is present",
    ),
    _ContentRule(
        "credential-assignment",
        re.compile(
            r"\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|password|passwd)\b"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{16,}",
            re.IGNORECASE,
        ),
        "a credential-like assignment is present",
    ),
    _ContentRule(
        "windows-home-path",
        re.compile(r"(?:[A-Z]:)?[\\/]+Users[\\/]+(?!Public(?:[\\/]|$))[^\\/\s\"'<>]+", re.IGNORECASE),
        "an absolute user-profile path is present",
    ),
    _ContentRule(
        "unix-home-path",
        re.compile(r"(?:/home|/Users)/(?!(?:public|shared)(?:/|$))[^/\s\"'<>]+", re.IGNORECASE),
        "an absolute user home path is present",
    ),
)
_BINARY_RULE_NAMES = {
    "aws-access-key",
    "discord-webhook",
    "github-token",
    "openai-token",
    "private-key",
    "slack-token",
    "unix-home-path",
    "windows-home-path",
}
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,}|invalid)\b", re.IGNORECASE)
_ALLOWED_EMAIL_DOMAINS = {"example.com", "example.net", "example.org", "invalid", "users.noreply.github.com"}
_CAPTURE_DIGEST_FIELD = '"input_' + 'sha256"'


class SafetyScanError(RuntimeError):
    pass


def _normalized_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.removeprefix("./")


def _path_findings(path: str, size: int) -> list[Finding]:
    normalized = _normalized_path(path)
    pure_path = PurePosixPath(normalized)
    parts = tuple(part.casefold() for part in pure_path.parts)
    filename = pure_path.name.casefold()
    suffix = pure_path.suffix.casefold()
    findings: list[Finding] = []

    forbidden_directories = sorted(set(parts[:-1]) & _FORBIDDEN_DIRECTORIES)
    if forbidden_directories:
        findings.append(
            Finding(
                rule="private-data-directory",
                path=normalized,
                detail=f"file is under blocked directory {forbidden_directories[0]!r}",
            )
        )

    is_example = filename in {".env.example", ".public-safety.local.example"}
    if not is_example and (filename in _FORBIDDEN_FILENAMES or filename.startswith(".env.")):
        findings.append(
            Finding(rule="sensitive-filename", path=normalized, detail="filename is reserved for local-only data")
        )

    if suffix in _FORBIDDEN_SUFFIXES:
        findings.append(
            Finding(rule="sensitive-file-type", path=normalized, detail=f"{suffix} files must remain outside Git")
        )

    if suffix in _MEDIA_SUFFIXES and filename.startswith(_CAPTURE_FILE_PREFIXES):
        findings.append(
            Finding(rule="capture-media", path=normalized, detail="capture-like media must remain outside Git")
        )

    if size > MAX_TRACKED_FILE_BYTES:
        findings.append(
            Finding(
                rule="oversized-file",
                path=normalized,
                detail=f"tracked file exceeds {MAX_TRACKED_FILE_BYTES // (1024 * 1024)} MiB",
            )
        )
    return findings


def _email_allowed(match: re.Match[str]) -> bool:
    domain = match.group(1).casefold()
    return domain in _ALLOWED_EMAIL_DOMAINS or domain.endswith(".invalid")


def _local_deny_findings(path: str, payload: bytes, text: str | None, deny_terms: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    folded_lines = [line.casefold() for line in text.splitlines()] if text is not None else []
    for index, term in enumerate(deny_terms, start=1):
        matched_text = False
        if text is not None:
            folded_term = term.casefold()
            for line_number, line in enumerate(folded_lines, start=1):
                if folded_term in line:
                    matched_text = True
                    findings.append(
                        Finding(
                            rule="local-denylist",
                            path=path,
                            line=line_number,
                            detail=f"matched local denylist entry {index}",
                        )
                    )
        if matched_text:
            continue
        variants = {term, term.casefold(), term.upper()}
        encodings = {
            variant.encode(encoding, errors="ignore")
            for variant in variants
            for encoding in ("utf-8", "utf-16-le", "utf-16-be")
        }
        if any(encoded and encoded in payload for encoded in encodings):
            findings.append(
                Finding(
                    rule="local-denylist", path=path, detail=f"binary metadata matched local denylist entry {index}"
                )
            )
    return findings


def _content_findings(path: str, payload: bytes, deny_terms: Sequence[str]) -> list[Finding]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = None

    findings = _local_deny_findings(path, payload, text, deny_terms)
    if text is None:
        binary_text = payload.decode("latin-1", errors="ignore")
        for rule in _CONTENT_RULES:
            if rule.name in _BINARY_RULE_NAMES and rule.pattern.search(binary_text):
                findings.append(Finding(rule=rule.name, path=path, detail=rule.detail))
        return findings

    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in _CONTENT_RULES:
            if rule.pattern.search(line):
                findings.append(Finding(rule=rule.name, path=path, line=line_number, detail=rule.detail))
        for match in _EMAIL_PATTERN.finditer(line):
            if not _email_allowed(match):
                findings.append(
                    Finding(
                        rule="email-address",
                        path=path,
                        line=line_number,
                        detail="a non-placeholder email address is present",
                    )
                )
        if _CAPTURE_DIGEST_FIELD in line.casefold():
            findings.append(
                Finding(
                    rule="capture-fingerprint",
                    path=path,
                    line=line_number,
                    detail="a private input digest field is present",
                )
            )
    if PurePosixPath(path).suffix.casefold() == ".json":
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            structured = None
        if isinstance(structured, dict):
            input_metadata = structured.get("input")
            if isinstance(input_metadata, dict) and isinstance(input_metadata.get("sha256"), str):
                findings.append(
                    Finding(rule="capture-fingerprint", path=path, detail="a private replay input digest is present")
                )
            tts_metadata = structured.get("tts")
            if (
                isinstance(structured.get("fingerprint"), str)
                and isinstance(tts_metadata, dict)
                and ("raw_lines" in tts_metadata or "framed_lines" in tts_metadata)
            ):
                findings.append(
                    Finding(
                        rule="capture-artifact", path=path, detail="an automatic failure-capture manifest is present"
                    )
                )
    return findings


def scan_items(items: Mapping[str, bytes], deny_terms: Sequence[str] = ()) -> list[Finding]:
    findings: list[Finding] = []
    for original_path, payload in sorted(items.items()):
        path = _normalized_path(original_path)
        findings.extend(_path_findings(path, len(payload)))
        findings.extend(_content_findings(path, payload, deny_terms))
    return _deduplicate(findings)


def _decoded_item(items: Mapping[str, bytes], path: str) -> str:
    payload = items.get(path)
    if payload is None:
        return ""
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ""


def _mit_data_source_findings(items: Mapping[str, bytes], sources: Mapping[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    readme_text = _decoded_item(items, D2CORE_ATTRIBUTION_PATH).casefold()
    notice_text = _decoded_item(items, THIRD_PARTY_NOTICE_PATH)
    policy_text = _decoded_item(items, THIRD_PARTY_POLICY_PATH).casefold()

    for key, (display_name, repository, public_url, copyright_notice) in _MIT_DATA_SOURCES.items():
        metadata = sources.get(key)
        if not isinstance(metadata, dict):
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=THIRD_PARTY_MANIFEST,
                    detail=f"{display_name} source metadata is missing",
                )
            )
            continue
        if metadata.get("repository") != repository:
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=THIRD_PARTY_MANIFEST,
                    detail=f"{display_name} repository provenance is missing or unexpected",
                )
            )
        if display_name.casefold() not in readme_text or public_url.casefold() not in readme_text:
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=D2CORE_ATTRIBUTION_PATH,
                    detail=f"README does not contain the required {display_name} attribution",
                )
            )
        if display_name.casefold() not in policy_text or "mit license" not in policy_text:
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=THIRD_PARTY_POLICY_PATH,
                    detail=f"third-party data policy does not document {display_name}",
                )
            )
        required_notice_text = (display_name, public_url, copyright_notice, "Permission is hereby granted")
        if any(value not in notice_text for value in required_notice_text):
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=THIRD_PARTY_NOTICE_PATH,
                    detail=f"complete MIT notice for {display_name} is missing",
                )
            )
    return findings


def third_party_redistribution_findings(items: Mapping[str, bytes]) -> list[Finding]:
    manifest_payload = items.get(THIRD_PARTY_MANIFEST)
    if manifest_payload is None:
        return [
            Finding(
                rule="third-party-license",
                path=THIRD_PARTY_MANIFEST,
                detail="source manifest is missing, so redistribution cannot be verified",
            )
        ]
    try:
        manifest = json.loads(manifest_payload.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        return [
            Finding(
                rule="third-party-license",
                path=THIRD_PARTY_MANIFEST,
                detail="source manifest is unreadable, so redistribution cannot be verified",
            )
        ]
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        return [
            Finding(
                rule="third-party-license",
                path=THIRD_PARTY_MANIFEST,
                detail="source metadata is missing, so redistribution cannot be verified",
            )
        ]
    d2core = sources.get("d2core")
    if not isinstance(d2core, dict):
        return [
            Finding(
                rule="third-party-license",
                path=THIRD_PARTY_MANIFEST,
                detail="D2Core source metadata is missing, so redistribution cannot be verified",
            )
        ]
    authorization = d2core.get("authorization")
    if not isinstance(authorization, dict):
        return [
            Finding(
                rule="third-party-license", path=THIRD_PARTY_MANIFEST, detail="D2Core redistribution status is missing"
            )
        ]

    findings: list[Finding] = []
    if authorization.get("public_redistribution") != "documented":
        findings.append(
            Finding(
                rule="third-party-license",
                path=THIRD_PARTY_MANIFEST,
                detail="D2Core public redistribution status is not documented",
            )
        )
    reference = authorization.get("reference")
    reference_path = reference.split("#", maxsplit=1)[0] if isinstance(reference, str) else ""
    reference_payload = items.get(reference_path) if reference_path else None
    if reference_payload is None:
        findings.append(
            Finding(
                rule="third-party-license",
                path=THIRD_PARTY_MANIFEST,
                detail="D2Core publication reference is missing from the release tree",
            )
        )
    else:
        try:
            reference_text = reference_payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            reference_text = ""
        anchor = reference.partition("#")[2].casefold() if isinstance(reference, str) else ""
        headings = {
            re.sub(r"[^a-z0-9]+", "-", match.group(1).casefold()).strip("-")
            for line in reference_text.splitlines()
            if (match := re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line))
        }
        if not reference_text or (anchor and anchor not in headings):
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=reference_path,
                    detail="D2Core publication reference does not contain the declared section",
                )
            )
        if (
            authorization.get("public_redistribution") == "documented"
            and "public redistribution status: documented" not in reference_text.casefold()
        ):
            findings.append(
                Finding(
                    rule="third-party-license",
                    path=reference_path,
                    detail="D2Core publication document does not declare public redistribution as documented",
                )
            )
    readme_text = _decoded_item(items, D2CORE_ATTRIBUTION_PATH).casefold()
    if "d2core" not in readme_text or "https://www.d2core.com" not in readme_text:
        findings.append(
            Finding(
                rule="third-party-license",
                path=D2CORE_ATTRIBUTION_PATH,
                detail="README does not contain the required D2Core source attribution",
            )
        )
    findings.extend(_mit_data_source_findings(items, sources))
    return findings


def _deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    unique = {(finding.rule, finding.path, finding.line, finding.detail): finding for finding in findings}
    return sorted(unique.values(), key=lambda finding: (finding.path, finding.line or 0, finding.rule, finding.detail))


def _run_git(arguments: Sequence[str], *, cwd: Path | None = None) -> bytes:
    process = subprocess.run(["git", *arguments], cwd=cwd, check=False, capture_output=True)
    if process.returncode != 0:
        message = process.stderr.decode("utf-8", errors="replace").strip()
        error_message = f"git {' '.join(arguments)} failed: {message}"
        raise SafetyScanError(error_message)
    return process.stdout


def _git_root() -> Path:
    return Path(_run_git(["rev-parse", "--show-toplevel"]).decode("utf-8").strip())


def _tree_items(revision: str) -> dict[str, bytes]:
    raw_entries = _run_git(["ls-tree", "-r", "-z", "--full-tree", revision])
    entries: list[tuple[bytes, str]] = []
    for raw_entry in raw_entries.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", maxsplit=1)
        _mode, object_type, object_id = metadata.split(maxsplit=2)
        if object_type == b"blob":
            entries.append((object_id, raw_path.decode("utf-8", errors="surrogateescape")))

    queries = b"".join(object_id + b"\n" for object_id, _path in entries)
    process = subprocess.run(["git", "cat-file", "--batch"], input=queries, check=False, capture_output=True)
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        message = f"git cat-file --batch failed: {detail}"
        raise SafetyScanError(message)

    output = io.BytesIO(process.stdout)
    items: dict[str, bytes] = {}
    for expected_object_id, path in entries:
        header = output.readline().rstrip(b"\n").split()
        if len(header) != 3 or header[0] != expected_object_id or header[1] != b"blob":
            message = f"unexpected git cat-file response while reading {path}"
            raise SafetyScanError(message)
        size = int(header[2])
        payload = output.read(size)
        if len(payload) != size or output.read(1) != b"\n":
            message = f"truncated git blob while reading {path}"
            raise SafetyScanError(message)
        items[_normalized_path(path)] = payload
    return items


def _index_items() -> dict[str, bytes]:
    tree = _run_git(["write-tree"]).decode("ascii").strip()
    return _tree_items(tree)


def _filesystem_items(root: Path) -> dict[str, bytes]:
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        message = f"scan path is not a directory: {resolved_root}"
        raise SafetyScanError(message)
    items: dict[str, bytes] = {}
    for path in resolved_root.rglob("*"):
        relative = path.relative_to(resolved_root)
        if ".git" in relative.parts or not path.is_file():
            continue
        items[_normalized_path(relative.as_posix())] = path.read_bytes()
    return items


def _load_deny_terms(path: Path | None) -> tuple[str, ...]:
    if path is None or not path.exists():
        return ()
    terms = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            terms.append(value)
    return tuple(dict.fromkeys(terms))


def _git_repository_metadata_findings(repo_root: Path, *, expected_branch: str) -> list[Finding]:
    findings: list[Finding] = []
    git_dir = Path(
        _run_git(["rev-parse", "--absolute-git-dir"], cwd=repo_root).decode("utf-8", errors="replace").strip()
    )

    findings.extend([
        Finding(
            rule="git-transient-metadata",
            path=f".git/{filename}",
            detail="prepared release must not retain transient Git operation metadata",
        )
        for filename in ("FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REBASE_HEAD")
        if (git_dir / filename).exists()
    ])

    for directory in ("logs", "refs/original"):
        metadata_path = git_dir / directory
        if metadata_path.is_dir() and any(path.is_file() for path in metadata_path.rglob("*")):
            findings.append(
                Finding(
                    rule="git-transient-metadata",
                    path=f".git/{directory}",
                    detail="prepared release must not retain reflogs or backup refs",
                )
            )

    refs = set(
        _run_git(["for-each-ref", "--format=%(refname)"], cwd=repo_root).decode("utf-8", errors="replace").splitlines()
    )
    expected_refs = {f"refs/heads/{expected_branch}"}
    if refs != expected_refs:
        findings.append(
            Finding(
                rule="git-ref-set",
                path=".git/refs",
                detail=f"prepared release must contain only refs/heads/{expected_branch}",
            )
        )

    unreachable = (
        _run_git(["fsck", "--full", "--no-reflogs", "--unreachable", "--no-progress"], cwd=repo_root)
        .decode("utf-8", errors="replace")
        .splitlines()
    )
    if unreachable:
        findings.append(
            Finding(
                rule="git-unreachable-object",
                path=".git/objects",
                detail="prepared release contains unreachable Git objects",
            )
        )
    return findings


def _public_metadata_findings(repo_root: Path) -> list[Finding]:
    findings = _git_repository_metadata_findings(repo_root, expected_branch="main")
    commit_count = int(_run_git(["rev-list", "--all", "--count"], cwd=repo_root).decode("ascii").strip())
    if commit_count != 1:
        findings.append(
            Finding(
                rule="public-history",
                path=".git",
                detail="public export must contain exactly one commit and no inherited history",
            )
        )

    remotes = _run_git(["remote"], cwd=repo_root).decode("utf-8").splitlines()
    if remotes:
        findings.append(
            Finding(rule="public-remote", path=".git/config", detail="public export must not inherit any remote")
        )

    fields = (
        _run_git(["log", "-1", "--format=%an%x1f%ae%x1f%cn%x1f%ce%x1f%aI%x1f%cI"], cwd=repo_root)
        .decode("utf-8")
        .strip()
        .split("\x1f")
    )
    expected_identity = [PUBLIC_AUTHOR_NAME, PUBLIC_AUTHOR_EMAIL, PUBLIC_AUTHOR_NAME, PUBLIC_AUTHOR_EMAIL]
    if fields[:4] != expected_identity:
        findings.append(
            Finding(
                rule="public-identity",
                path=".git",
                detail="public commit must use the neutral release author and committer",
            )
        )
    if len(fields) != 6 or any(not value.endswith(("+00:00", "Z")) for value in fields[4:]):
        findings.append(Finding(rule="public-timestamp", path=".git", detail="public commit timestamps must use UTC"))

    head = _run_git(["rev-list", "--parents", "-n", "1", "HEAD"], cwd=repo_root).decode("ascii").split()
    if len(head) != 1:
        findings.append(Finding(rule="public-history", path=".git", detail="public commit must be a root commit"))
    return findings


def _fork_metadata_findings(
    repo_root: Path, *, base_revision: str, expected_branch: str, expected_author_name: str, expected_author_email: str
) -> list[Finding]:
    findings = _git_repository_metadata_findings(repo_root, expected_branch=expected_branch)
    base_commit = _run_git(["rev-parse", f"{base_revision}^{{commit}}"], cwd=repo_root).decode("ascii").strip()
    branch = _run_git(["symbolic-ref", "--short", "HEAD"], cwd=repo_root).decode("utf-8").strip()
    if branch != expected_branch:
        findings.append(
            Finding(rule="fork-branch", path=".git/HEAD", detail=f"release branch must be named {expected_branch!r}")
        )

    ancestor_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_commit, "HEAD"], cwd=repo_root, check=False, capture_output=True
    )
    if ancestor_check.returncode not in {0, 1}:
        message = ancestor_check.stderr.decode("utf-8", errors="replace").strip()
        error_message = f"git merge-base --is-ancestor failed: {message}"
        raise SafetyScanError(error_message)
    if ancestor_check.returncode == 1:
        findings.append(
            Finding(rule="fork-history", path=".git", detail="the configured upstream base is not an ancestor of HEAD")
        )

    release_commits = (
        _run_git(["rev-list", "--reverse", f"{base_commit}..HEAD"], cwd=repo_root).decode("ascii").splitlines()
    )
    if len(release_commits) != 1:
        findings.append(
            Finding(
                rule="fork-history",
                path=".git",
                detail="prepared fork must contain exactly one release commit after the upstream base",
            )
        )

    extra_history = _run_git(["rev-list", "--all", "--not", "HEAD"], cwd=repo_root).decode("ascii").splitlines()
    if extra_history:
        findings.append(
            Finding(
                rule="fork-history",
                path=".git",
                detail="prepared fork contains additional refs or history not reachable from HEAD",
            )
        )

    remotes = _run_git(["remote"], cwd=repo_root).decode("utf-8").splitlines()
    if remotes:
        findings.append(
            Finding(rule="fork-remote", path=".git/config", detail="prepared fork must not inherit any remote")
        )

    expected_identity = [expected_author_name, expected_author_email, expected_author_name, expected_author_email]
    for commit in release_commits:
        fields = (
            _run_git(["log", "-1", "--format=%an%x1f%ae%x1f%cn%x1f%ce%x1f%aI%x1f%cI", commit], cwd=repo_root)
            .decode("utf-8")
            .strip()
            .split("\x1f")
        )
        if fields[:4] != expected_identity:
            findings.append(
                Finding(
                    rule="fork-identity",
                    path=".git",
                    detail="release commit does not use the configured public author and committer",
                )
            )
        if len(fields) != 6 or any(not value.endswith(("+00:00", "Z")) for value in fields[4:]):
            findings.append(
                Finding(rule="fork-timestamp", path=".git", detail="release commit timestamps must use UTC")
            )

    if len(release_commits) == 1:
        head = _run_git(["rev-list", "--parents", "-n", "1", "HEAD"], cwd=repo_root).decode("ascii").split()
        if len(head) != 2 or head[1] != base_commit:
            findings.append(
                Finding(
                    rule="fork-history",
                    path=".git",
                    detail="release commit must be a direct child of the configured upstream base",
                )
            )
    return findings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reject private data and identity fingerprints before publication.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--index", action="store_true", help="Scan the complete Git index.")
    source.add_argument("--tree", metavar="REV", help="Scan a committed Git tree, such as HEAD.")
    source.add_argument("--path", type=Path, help="Scan every file under a filesystem directory except .git.")
    source.add_argument(
        "--public-release", action="store_true", help="Scan HEAD and require one neutral root commit with no remote."
    )
    source.add_argument(
        "--fork-release",
        action="store_true",
        help="Scan HEAD and require one public-identity commit directly above an upstream base.",
    )
    parser.add_argument("--denylist", type=Path, help="Optional local literal denylist; findings never print values.")
    parser.add_argument("--fork-base", help="Upstream revision used as the parent of a prepared fork release.")
    parser.add_argument("--expected-branch", help="Required branch name for a prepared fork release.")
    parser.add_argument("--expected-author-name", help="Required author and committer name for fork release commits.")
    parser.add_argument("--expected-author-email", help="Required author and committer email for fork release commits.")
    parser.add_argument(
        "--require-third-party-redistribution",
        action="store_true",
        help="Block while bundled third-party data lacks a documented publication and attribution status.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def _require_fork_options(arguments: argparse.Namespace) -> None:
    if not arguments.fork_release:
        return
    required_options = {
        "--fork-base": arguments.fork_base,
        "--expected-branch": arguments.expected_branch,
        "--expected-author-name": arguments.expected_author_name,
        "--expected-author-email": arguments.expected_author_email,
    }
    missing = [option for option, value in required_options.items() if not value]
    if missing:
        message = f"{', '.join(missing)} required with --fork-release"
        raise ValueError(message)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        _require_fork_options(arguments)
        repo_root = _git_root() if arguments.path is None else Path.cwd()
        denylist = arguments.denylist
        if denylist is None:
            candidate = repo_root / ".public-safety.local"
            denylist = candidate if candidate.exists() else None
        deny_terms = _load_deny_terms(denylist)

        if arguments.index:
            items = _index_items()
        elif arguments.tree:
            items = _tree_items(arguments.tree)
        elif arguments.path is not None:
            items = _filesystem_items(arguments.path)
        else:
            items = _tree_items("HEAD")

        findings = scan_items(items, deny_terms)
        if arguments.require_third_party_redistribution or arguments.public_release or arguments.fork_release:
            findings.extend(third_party_redistribution_findings(items))
        if arguments.public_release:
            findings.extend(_public_metadata_findings(_git_root()))
        if arguments.fork_release:
            findings.extend(
                _fork_metadata_findings(
                    _git_root(),
                    base_revision=arguments.fork_base,
                    expected_branch=arguments.expected_branch,
                    expected_author_name=arguments.expected_author_name,
                    expected_author_email=arguments.expected_author_email,
                )
            )
        findings = _deduplicate(findings)
    except (OSError, SafetyScanError, ValueError) as error:
        print(f"Public safety scan could not run: {error}", file=sys.stderr)
        return 2

    if findings:
        print(f"Public safety scan failed with {len(findings)} finding(s):", file=sys.stderr)
        for finding in findings[:200]:
            location = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path
            print(f"- [{finding.rule}] {location}: {finding.detail}", file=sys.stderr)
        if len(findings) > 200:
            print(f"- {len(findings) - 200} additional finding(s) omitted", file=sys.stderr)
        return 1

    if not arguments.quiet:
        print(f"Public safety scan passed ({len(items)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
