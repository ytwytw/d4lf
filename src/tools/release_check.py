"""Check locale readiness and declared redistribution restrictions before publication.

Locale gaps block publication unless an exact-match acceptance ledger documents each one as a
known, fail-closed limitation (see ``release_acceptance``). Bundled-source provenance and
unreadable reports always block.
"""

import json
from pathlib import Path

from src.tools.release_acceptance import AcceptanceResult, ReadinessFailure, apply_acceptance

_QUALITY = "quality-report.json"


def _blocking(key: str, message: str) -> ReadinessFailure:
    return ReadinessFailure(key, message, waivable=False)


def _check_bundled_sources(root: Path) -> list[ReadinessFailure]:
    failures: list[ReadinessFailure] = []
    directory = root / "assets/equipment_knowledge"
    if not directory.exists():
        return failures
    # Provenance belongs to numeric build indexes, not their item/affix shards.
    catalogs = sorted(path for path in directory.glob("catalog-*.json") if path.stem.removeprefix("catalog-").isdigit())
    if not catalogs:
        return [_blocking("bundled:missing", "equipment_knowledge: missing bundled catalog provenance")]
    for path in catalogs:
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            failures.append(
                _blocking(f"bundled:{path.name}", f"{path.name}: cannot read bundled source provenance ({error})")
            )
            continue
        sources = catalog.get("sources") if isinstance(catalog, dict) else None
        if not isinstance(sources, list) or not sources:
            failures.append(
                _blocking(f"bundled:{path.name}", f"{path.name}: bundled catalog sources must be a nonempty list")
            )
            continue
        for source in sources:
            if not isinstance(source, dict):
                failures.append(_blocking(f"bundled:{path.name}", f"{path.name}: invalid bundled source record"))
                continue
            # Enforce the declared restriction on the shipped D2Core snapshot; unrelated
            # sources without this marker keep their existing license/notice workflow.
            if source.get("provider") != "D2Core" and "public_redistribution" not in source:
                continue
            label = f"{path.name}: {source.get('provider', 'unknown')} / {source.get('file', 'unknown')}"
            if source.get("public_redistribution") != "verified":
                failures.append(_blocking(f"bundled:{label}", f"{label}: public redistribution is not verified"))
                continue
            evidence = source.get("public_redistribution_evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                failures.append(_blocking(f"bundled:{label}", f"{label}: public redistribution evidence is missing"))
    return failures


def _pairs(value: object) -> str:
    return ",".join(f"{key}={item}" for key, item in sorted(value.items())) if isinstance(value, dict) else "unknown"


def _quality_facts(report: dict[str, object]) -> list[ReadinessFailure]:
    """The concrete reasons behind source_quality_ok, so a new or changed reason is a new failure."""
    facts: list[ReadinessFailure] = []
    unresolved = report.get("unresolved", [])
    if not isinstance(unresolved, list) or any(not isinstance(entry, dict) for entry in unresolved):
        return [_blocking(f"{_QUALITY}:malformed", f"{_QUALITY}: unresolved must be a list of records")]
    for entry in unresolved:
        stable_id = entry.get("stable_id")
        facts.append(
            ReadinessFailure(f"{_QUALITY}:unresolved:{stable_id}", f"{_QUALITY}: unresolved record {stable_id}")
        )
    summary = report.get("summary")
    if isinstance(summary, dict) and summary.get("source_builds_match") is False:
        builds = _pairs(report.get("source_builds"))
        facts.append(
            ReadinessFailure(
                f"{_QUALITY}:source_builds_mismatch:{builds}", f"{_QUALITY}: source builds differ ({builds})"
            )
        )
    companion = report.get("companion_quality")
    if isinstance(companion, dict) and companion.get("ok") is False:
        detail = _pairs(companion.get("summary"))
        facts.append(
            ReadinessFailure(f"{_QUALITY}:companion_quality:{detail}", f"{_QUALITY}: companion data quality ({detail})")
        )
    selected = report.get("selected_quality")
    collisions = selected.get("alias_collisions", []) if isinstance(selected, dict) else []
    for collision in collisions if isinstance(collisions, list) else []:
        if isinstance(collision, dict):
            alias = f"{collision.get('namespace')}:{collision.get('normalized_alias')}"
            facts.append(
                ReadinessFailure(f"{_QUALITY}:alias_collision:{alias}", f"{_QUALITY}: alias collision {alias}")
            )
    conflicts = report.get("translation_conflicts")
    if conflicts:
        count = len(conflicts) if isinstance(conflicts, list) else conflicts
        facts.append(ReadinessFailure(f"{_QUALITY}:translation_conflicts:{count}", f"{_QUALITY}: {count} conflicts"))
    return facts


def _locale_failures(root: Path, filename: str) -> list[ReadinessFailure]:
    path = root / "assets/lang/zhCN" / filename
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [_blocking(f"{filename}:unreadable", f"{filename}: cannot read readiness report ({error})")]
    if not isinstance(report, dict):
        return [_blocking(f"{filename}:unreadable", f"{filename}: readiness report must be an object")]
    failures: list[ReadinessFailure] = []
    if report.get("runtime_ready") is not True:
        failures.append(ReadinessFailure(f"{filename}:runtime_ready", f"{filename}: runtime_ready is not true"))
    quality = report.get("summary") if filename == _QUALITY else report
    if not isinstance(quality, dict) or quality.get("source_quality_ok") is not True:
        failures.append(ReadinessFailure(f"{filename}:source_quality_ok", f"{filename}: source_quality_ok is not true"))
    blockers = report.get("readiness_blockers", [])
    if not isinstance(blockers, list) or any(not isinstance(blocker, str) for blocker in blockers):
        return [*failures, _blocking(f"{filename}:malformed", f"{filename}: readiness_blockers must be strings")]
    failures += [
        ReadinessFailure(
            f"{filename}:readiness_blocker:{blocker}", f"{filename}: unresolved readiness_blocker: {blocker}"
        )
        for blocker in blockers
    ]
    return failures + (_quality_facts(report) if filename == _QUALITY else [])


def collect_readiness_failures(root: Path) -> list[ReadinessFailure]:
    """Every current readiness failure, before any documented limitation is accepted."""
    failures = [failure for name in ("manifest.json", _QUALITY) for failure in _locale_failures(root, name)]
    return failures + _check_bundled_sources(root)


def evaluate_release_readiness(root: Path) -> AcceptanceResult:
    return apply_acceptance(root, collect_readiness_failures(root))


def check_release_readiness(root: Path) -> list[str]:
    """Blocking messages; empty when publication may proceed."""
    return list(evaluate_release_readiness(root).blocking)


def main() -> int:
    result = evaluate_release_readiness(Path(__file__).resolve().parents[2])
    if result.blocking:
        print("Publication blocked. Build-only artifacts may still be generated for testing:")
        for failure in result.blocking:
            print(f"- {failure}")
        return 1
    if result.accepted:
        print("Publication readiness checks passed with accepted known limitations (live_validated=false):")
        for limitation in result.accepted:
            print(f"- {limitation.id}: {limitation.limitation}")
        return 0
    print("Publication readiness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
