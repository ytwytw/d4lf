"""Path and file-type rules for public repository content."""

from pathlib import PurePosixPath

from src.tools.public_safety.models import Finding

MAX_TRACKED_FILE_BYTES = 25 * 1024 * 1024

_PRIVATE_DIRECTORIES = {
    ".agents",
    ".claude",
    ".codex",
    ".scratch",
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
_PRIVATE_FILENAMES = {
    ".env",
    ".npmrc",
    ".public-safety.local",
    ".pypirc",
    "agent.md",
    "claude.md",
    "codex.md",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "params.ini",
    "secrets.json",
    "verified_zhcn.json",
}
_PRIVATE_SUFFIXES = {
    ".7z",
    ".avi",
    ".bak",
    ".cer",
    ".crt",
    ".db",
    ".der",
    ".dmp",
    ".dump",
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
_CAPTURE_PREFIXES = ("capture_", "dump_", "info_", "obs_", "screen_record", "screenshot")
_REPORT_MARKERS = ("gitleaks-report", "public-safety-report", "secret-scan-report", "secret-scan-results")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def path_findings(path: str, size: int) -> list[Finding]:
    normalized = normalize_path(path)
    pure_path = PurePosixPath(normalized)
    parts = tuple(part.casefold() for part in pure_path.parts)
    filename = pure_path.name.casefold()
    suffix = pure_path.suffix.casefold()
    findings: list[Finding] = []

    blocked_directories = sorted(set(parts[:-1]) & _PRIVATE_DIRECTORIES)
    public_capture_packages = ("src/perception/capture/", "tests/perception/capture/")
    if normalized.startswith(public_capture_packages):
        blocked_directories = [directory for directory in blocked_directories if directory != "capture"]
    if blocked_directories:
        findings.append(
            Finding(
                "private-data-directory",
                normalized,
                f"remove this file from Git; {blocked_directories[0]!r} is reserved for local-only data",
            )
        )

    is_example = filename in {".env.example", ".public-safety.local.example"}
    private_agent_file = filename == "agents.md" and normalized != "AGENTS.md"
    if not is_example and (filename in _PRIVATE_FILENAMES or filename.startswith(".env.") or private_agent_file):
        findings.append(
            Finding(
                "sensitive-filename",
                normalized,
                "remove this local/private file from Git and add a matching ignore rule",
            )
        )

    if suffix in _PRIVATE_SUFFIXES:
        findings.append(
            Finding(
                "sensitive-file-type",
                normalized,
                f"remove this {suffix or 'private'} artifact from Git and keep it outside the repository",
            )
        )

    if suffix in _MEDIA_SUFFIXES and filename.startswith(_CAPTURE_PREFIXES):
        findings.append(
            Finding(
                "capture-media",
                normalized,
                "remove this screenshot/capture from Git and store it in the local capture directory",
            )
        )

    if any(marker in filename for marker in _REPORT_MARKERS):
        findings.append(
            Finding(
                "scanner-report",
                normalized,
                "remove generated security scan reports from Git; keep reports in CI or local storage",
            )
        )

    if size > MAX_TRACKED_FILE_BYTES:
        findings.append(
            Finding(
                "oversized-file",
                normalized,
                f"remove or externally publish this file; tracked files must be at most "
                f"{MAX_TRACKED_FILE_BYTES // (1024 * 1024)} MiB",
            )
        )
    return findings
