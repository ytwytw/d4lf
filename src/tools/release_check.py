"""Fail publication when the checked-in locale audit records unresolved release blockers."""

import json
from pathlib import Path


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
    return failures


def main() -> int:
    failures = check_release_readiness(Path(__file__).resolve().parents[2])
    if failures:
        print("Publication blocked. Build-only artifacts may still be generated for testing:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Locale publication readiness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
