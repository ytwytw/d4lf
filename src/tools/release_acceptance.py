"""Exact-match ledger of documented locale limitations that may ship without live-game validation.

Every currently failing waivable readiness check must be listed, every listed failure must still be
failing, and each limitation names regression tests that guard its fail-closed runtime behavior.
Unreadable reports and bundled-source provenance failures can never be accepted.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

ACCEPTANCE_PATH = Path("assets/lang/zhCN/release-acceptance.json")
_LEDGER = ACCEPTANCE_PATH.name
_ENTRY_FIELDS = {"id", "limitation", "live_validated", "failures", "runtime_guard"}
_LEDGER_FIELDS = {"schema_version", "locale", "basis", "accepted"}
_NODE_ID = re.compile(r"(tests/[\w./-]+\.py)((?:::[A-Za-z_]\w*)+)(\[.*\])?")


@dataclass(frozen=True)
class ReadinessFailure:
    key: str
    message: str
    waivable: bool = True


@dataclass(frozen=True)
class AcceptedLimitation:
    id: str
    limitation: str
    failures: tuple[str, ...]
    runtime_guard: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceResult:
    blocking: tuple[str, ...]
    accepted: tuple[AcceptedLimitation, ...] = ()


def _strings(value: object) -> tuple[str, ...] | None:
    """A non-empty list of unique, non-blank strings."""
    if not isinstance(value, list):
        return None
    items = tuple(item for item in value if isinstance(item, str) and item.strip())
    return items if items and len(items) == len(value) == len(set(items)) else None


def _guard_error(root: Path, node_id: str) -> str | None:
    match = _NODE_ID.fullmatch(node_id)
    if match is None:
        return "is not a pytest node id under tests/"
    path = root / match.group(1)
    if not path.is_file():
        return "names a missing test file"
    text = path.read_text(encoding="utf-8")
    for name in match.group(2).split("::")[1:]:
        if not re.search(rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b", text, re.MULTILINE):
            return f"names missing test {name}"
    return None


def _entry(root: Path, index: int, raw: object) -> tuple[AcceptedLimitation | None, list[str]]:
    where = f"{_LEDGER}: accepted[{index}]"
    if not isinstance(raw, dict) or set(raw) != _ENTRY_FIELDS:
        return None, [f"{where} must contain exactly {sorted(_ENTRY_FIELDS)}"]
    errors: list[str] = []
    if raw["live_validated"] is not False:
        errors.append(f"{where}.live_validated must be false; accepted limitations are never live-validated")
    errors += [
        f"{where}.{field} must be a non-empty string"
        for field in ("id", "limitation")
        if not isinstance(raw[field], str) or not raw[field].strip()
    ]
    failures, guards = _strings(raw["failures"]), _strings(raw["runtime_guard"])
    if failures is None:
        errors.append(f"{where}.failures must be a non-empty list of unique strings")
    if guards is None:
        errors.append(f"{where}.runtime_guard must be a non-empty list of unique pytest node ids")
    else:
        errors += [f"{where}.runtime_guard {node} {error}" for node in guards if (error := _guard_error(root, node))]
    if errors or failures is None or guards is None:
        return None, errors
    return AcceptedLimitation(raw["id"], raw["limitation"], failures, guards), []


def load_ledger(root: Path) -> tuple[list[AcceptedLimitation], list[str]]:
    try:
        data = json.loads((root / ACCEPTANCE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [], [f"{_LEDGER}: cannot read acceptance ledger ({error})"]
    if not isinstance(data, dict) or set(data) != _LEDGER_FIELDS:
        return [], [f"{_LEDGER}: ledger must contain exactly {sorted(_LEDGER_FIELDS)}"]
    errors: list[str] = []
    if data["schema_version"] != 1 or data["locale"] != "zhCN":
        errors.append(f"{_LEDGER}: unsupported schema_version or locale")
    if not isinstance(data["basis"], str) or not data["basis"].strip():
        errors.append(f"{_LEDGER}: basis must be a non-empty string")
    if not isinstance(data["accepted"], list):
        return [], [*errors, f"{_LEDGER}: accepted must be a list"]
    entries = []
    for index, raw in enumerate(data["accepted"]):
        entry, entry_errors = _entry(root, index, raw)
        errors += entry_errors
        if entry is not None:
            entries.append(entry)
    ids = [entry.id for entry in entries]
    keys = [key for entry in entries for key in entry.failures]
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        errors.append(f"{_LEDGER}: limitation ids and accepted failures must be unique")
    return entries, errors


def apply_acceptance(root: Path, failures: Sequence[ReadinessFailure]) -> AcceptanceResult:
    """Return blocking messages after waiving exactly the accepted, still-current failures."""
    blocking = [failure.message for failure in failures if not failure.waivable]
    waivable = {failure.key: failure for failure in failures if failure.waivable}
    if not (root / ACCEPTANCE_PATH).exists():
        return AcceptanceResult(tuple(blocking + [failure.message for failure in waivable.values()]))
    entries, errors = load_ledger(root)
    if errors:
        # An untrustworthy ledger waives nothing.
        return AcceptanceResult(tuple(blocking + errors + [failure.message for failure in waivable.values()]))
    accepted = {key for entry in entries for key in entry.failures}
    never_waivable = {failure.key for failure in failures if not failure.waivable}
    for key in sorted(accepted):
        if key in never_waivable:
            blocking.append(f"{_LEDGER}: {key} can never be accepted")
        elif key not in waivable:
            blocking.append(f"{_LEDGER}: stale acceptance for a failure that no longer occurs: {key}")
    blocking += [failure.message for key, failure in waivable.items() if key not in accepted]
    return AcceptanceResult(tuple(blocking), () if blocking else tuple(entries))


__all__ = [
    "ACCEPTANCE_PATH",
    "AcceptanceResult",
    "AcceptedLimitation",
    "ReadinessFailure",
    "apply_acceptance",
    "load_ledger",
]
