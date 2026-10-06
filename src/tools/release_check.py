"""Check locale readiness and declared redistribution restrictions before publication."""

import json
from pathlib import Path


def _check_bundled_sources(root: Path) -> list[str]:
    failures: list[str] = []
    directory = root / "assets/equipment_knowledge"
    if not directory.exists():
        return failures
    # Provenance belongs to numeric build indexes, not their item/affix shards.
    catalogs = sorted(path for path in directory.glob("catalog-*.json") if path.stem.removeprefix("catalog-").isdigit())
    if not catalogs:
        return ["equipment_knowledge: missing bundled catalog provenance"]
    for path in catalogs:
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            failures.append(f"{path.name}: cannot read bundled source provenance ({error})")
            continue
        sources = catalog.get("sources") if isinstance(catalog, dict) else None
        if not isinstance(sources, list) or not sources:
            failures.append(f"{path.name}: bundled catalog sources must be a nonempty list")
            continue
        for source in sources:
            if not isinstance(source, dict):
                failures.append(f"{path.name}: invalid bundled source record")
                continue
            # Enforce the declared restriction on the shipped D2Core snapshot; unrelated
            # sources without this marker keep their existing license/notice workflow.
            if source.get("provider") != "D2Core" and "public_redistribution" not in source:
                continue
            label = f"{path.name}: {source.get('provider', 'unknown')} / {source.get('file', 'unknown')}"
            if source.get("public_redistribution") != "verified":
                failures.append(f"{label}: public redistribution is not verified")
                continue
            evidence = source.get("public_redistribution_evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                failures.append(f"{label}: public redistribution evidence is missing")
    return failures


def check_release_readiness(root: Path) -> list[str]:
    failures: list[str] = []
    for filename in ("manifest.json", "quality-report.json"):
        path = root / "assets/lang/zhCN" / filename
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            failures.append(f"{filename}: cannot read readiness report ({error})")
            continue
        if not isinstance(report, dict):
            failures.append(f"{filename}: readiness report must be an object")
            continue
        if report.get("runtime_ready") is not True:
            failures.append(f"{filename}: runtime_ready is not true")
        quality = report.get("summary") if filename == "quality-report.json" else report
        if not isinstance(quality, dict) or quality.get("source_quality_ok") is not True:
            failures.append(f"{filename}: source_quality_ok is not true")
        blockers = report.get("readiness_blockers", [])
        if blockers:
            failures.append(f"{filename}: unresolved readiness_blockers: {blockers}")
    return failures + _check_bundled_sources(root)


def main() -> int:
    failures = check_release_readiness(Path(__file__).resolve().parents[2])
    if failures:
        print("Publication blocked. Build-only artifacts may still be generated for testing:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Publication readiness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
