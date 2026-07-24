from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from src.tools import d2core_data, locale_data_check

if TYPE_CHECKING:
    from pathlib import Path

BUILD_VERSION = "3.1.0.72592"


@dataclass(frozen=True)
class FixturePaths:
    source_lock: Path
    source_manifest: Path
    build_version: Path
    locale_manifest: Path
    source_file: Path
    locale_file: Path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _record(stable_id: str, source_text: str, translation: str | None = None) -> dict[str, str]:
    record = {"stable_id": stable_id, "source_sha256": _sha256_text(source_text)}
    record["text"] = source_text if translation is None else translation
    return record


def _make_fixture(tmp_path: Path) -> FixturePaths:
    d4data_dir = tmp_path / "d4data"
    d4data_dir.mkdir()
    build_version = d4data_dir / "buildVersion.txt"
    build_version.write_text(BUILD_VERSION + "\n", encoding="utf-8")
    source_file = d4data_dir / "json" / "source.json"
    _write_json(source_file, {"records": ["alpha", "beta"]})

    source_manifest = tmp_path / "source-manifest.json"
    _write_json(
        source_manifest,
        {
            "schema_version": 1,
            "build_version": BUILD_VERSION,
            "records": [_record("affix:alpha", "Alpha"), _record("affix:beta", "Beta")],
        },
    )

    source_lock = tmp_path / "source-lock.json"
    _write_json(
        source_lock,
        {
            "schema_version": 1,
            "build_version": BUILD_VERSION,
            "source_manifest": {"path": source_manifest.name, "sha256": _sha256_bytes(source_manifest.read_bytes())},
            "files": [{"path": "json/source.json", "sha256": _sha256_bytes(source_file.read_bytes())}],
        },
    )

    locale_dir = tmp_path / "locale"
    locale_file = locale_dir / "affixes.json"
    _write_json(locale_file, {"alpha": "阿尔法", "beta": "贝塔"})
    locale_manifest = locale_dir / "manifest.json"
    _write_json(
        locale_manifest,
        {
            "schema_version": 1,
            "build_version": BUILD_VERSION,
            "locale": "zhCN",
            "source_manifest_sha256": _sha256_bytes(source_manifest.read_bytes()),
            "files": [{"path": locale_file.name, "sha256": _sha256_bytes(locale_file.read_bytes())}],
            "records": [_record("affix:alpha", "Alpha", "阿尔法"), _record("affix:beta", "Beta", "贝塔")],
        },
    )
    return FixturePaths(
        source_lock=source_lock,
        source_manifest=source_manifest,
        build_version=build_version,
        locale_manifest=locale_manifest,
        source_file=source_file,
        locale_file=locale_file,
    )


def _enable_d2core_release_metadata(
    paths: FixturePaths,
    *,
    d2core_build: str = "72592",
    runtime_ready: bool = True,
    conflicts: int = 0,
    source_quality_ok: bool = True,
) -> None:
    keys = {(spec.name, locale) for spec in d2core_data.DATASET_SPECS for locale in d2core_data.LOCALES}
    payloads = {key: d2core_data.snapshot_filename(*key).encode() for key in keys}
    records = {key: ({},) * d2core_data.MINIMUM_RECORD_COUNTS[key[0]] for key in keys}
    urls = {key: d2core_data.dataset_url(d2core_build, *key) for key in keys}
    d2core_manifest = d2core_data.build_manifest(
        build_version=d2core_build,
        payloads=payloads,
        records=records,
        urls=urls,
        build_version_source={"kind": "pinned"},
    )
    d2core_manifest["translation_record_index"] = {
        "affix:fixture:1:x1": {"source_record_sha256": "a" * 64, "translation_sha256": _sha256_text("阿尔法")},
        "aspect:fixture:2:x1": {"source_record_sha256": "b" * 64, "translation_sha256": _sha256_text("阿尔法")},
    }

    source_manifest = json.loads(paths.source_manifest.read_text(encoding="utf-8"))
    source_manifest["sources"] = {"d2core": d2core_manifest}
    _write_json(paths.source_manifest, source_manifest)

    source_hash = _sha256_bytes(paths.source_manifest.read_bytes())
    source_lock = json.loads(paths.source_lock.read_text(encoding="utf-8"))
    source_lock["source_manifest"]["sha256"] = source_hash
    _write_json(paths.source_lock, source_lock)

    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    locale_manifest["source_manifest_sha256"] = source_hash
    locale_manifest["runtime_ready"] = runtime_ready
    locale_manifest["source_quality_ok"] = source_quality_ok
    locale_manifest["translation_conflicts"] = conflicts
    for record in locale_manifest["records"]:
        record["translation_source"] = {
            "provider": "locale_grammar",
            "source_id": record["stable_id"],
            "translation_sha256": _sha256_text(record["text"]),
        }
    _write_json(paths.locale_manifest, locale_manifest)


def _check(paths: FixturePaths) -> dict[str, object]:
    return locale_data_check.check_locale_data(
        source_lock=paths.source_lock, build_version=paths.build_version, locale_manifest=paths.locale_manifest
    )


def _issues(report: dict[str, object]) -> list[dict[str, object]]:
    issues = report["issues"]
    assert isinstance(issues, list)
    return cast("list[dict[str, object]]", issues)


def test_valid_fixture_passes_and_cli_emits_json(tmp_path: Path, capsys) -> None:
    paths = _make_fixture(tmp_path)

    exit_code = locale_data_check.main([
        "--source-lock",
        str(paths.source_lock),
        "--build-version",
        str(paths.build_version),
        "--locale-manifest",
        str(paths.locale_manifest),
    ])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == locale_data_check.EXIT_OK
    assert report["ok"] is True
    assert report["status"] == "ok"
    assert report["summary"]["source_records"] == 2
    assert report["summary"]["locale_records"] == 2
    assert report["issues"] == []


def test_build_and_schema_mismatches_fail_validation(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    paths.build_version.write_text("3.1.1.99999\n", encoding="utf-8")
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    locale_manifest["schema_version"] = 2
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)

    assert report["exit_code"] == locale_data_check.EXIT_CHECK_FAILED
    assert {issue["code"] for issue in _issues(report)} >= {"build_mismatch", "schema_version_mismatch"}


def test_declared_source_and_locale_file_hashes_are_checked(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    _write_json(paths.source_file, {"records": ["changed"]})
    _write_json(paths.locale_file, {"alpha": "已更改"})

    report = _check(paths)
    file_hash_issues = [
        issue for issue in _issues(report) if issue["code"] == "hash_mismatch" and issue.get("hash_kind") == "file"
    ]

    assert report["exit_code"] == locale_data_check.EXIT_CHECK_FAILED
    assert {issue["input"] for issue in file_hash_issues} == {"source_lock", "locale_manifest"}


def test_stable_id_coverage_duplicates_and_ascii_placeholders_are_reported(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    locale_manifest["records"] = [
        _record("affix:alpha", "Alpha", "Alpha"),
        _record("affix:alpha", "Alpha", "阿尔法"),
        _record("affix:gamma", "Gamma", "伽马"),
    ]
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)
    findings = {(issue["code"], issue.get("stable_id")) for issue in _issues(report)}

    assert report["exit_code"] == locale_data_check.EXIT_CHECK_FAILED
    assert ("duplicate_record", "affix:alpha") in findings
    assert ("missing_record", "affix:beta") in findings
    assert ("new_record", "affix:gamma") in findings
    assert ("ascii_placeholder", "affix:alpha") in findings


def test_record_source_hash_mismatch_and_missing_translation_are_reported(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    locale_manifest["records"][0]["source_sha256"] = _sha256_text("Older Alpha")
    locale_manifest["records"][1]["text"] = ""
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)
    findings = {(issue["code"], issue.get("stable_id")) for issue in _issues(report)}

    assert ("hash_mismatch", "affix:alpha") in findings
    assert ("missing_translation", "affix:beta") in findings


def test_missing_record_hash_fails_closed(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    del locale_manifest["records"][0]["source_sha256"]
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)

    assert report["exit_code"] == locale_data_check.EXIT_CHECK_FAILED
    assert any(issue["code"] == "hash_missing" and issue.get("stable_id") == "affix:alpha" for issue in _issues(report))


def test_missing_source_manifest_hash_fails_closed(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    del locale_manifest["source_manifest_sha256"]
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)

    assert report["exit_code"] == locale_data_check.EXIT_CHECK_FAILED
    assert any(
        issue["code"] == "hash_missing" and issue.get("hash_kind") == "source_manifest" for issue in _issues(report)
    )


def test_embedded_source_manifest_records_are_supported(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    source_manifest = json.loads(paths.source_manifest.read_text(encoding="utf-8"))
    source_lock = {
        **source_manifest,
        "files": [{"path": "json/source.json", "sha256": _sha256_bytes(paths.source_file.read_bytes())}],
    }
    _write_json(paths.source_lock, source_lock)

    report = _check(paths)

    assert report["exit_code"] == locale_data_check.EXIT_OK
    inputs = report["inputs"]
    assert isinstance(inputs, dict)
    inputs = cast("dict[str, object]", inputs)
    assert inputs["source_manifest"] is None


def test_d2core_release_metadata_and_translation_provenance_are_fail_closed(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    _enable_d2core_release_metadata(paths)

    assert _check(paths)["exit_code"] == locale_data_check.EXIT_OK

    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    del locale_manifest["records"][0]["translation_source"]
    locale_manifest["records"][1]["translation_source"]["translation_sha256"] = "0" * 64
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)
    assert {issue["code"] for issue in _issues(report)} == {
        "translation_provenance_missing",
        "translation_hash_mismatch",
    }


def test_d2core_translation_provenance_must_match_locked_record_and_dataset(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    _enable_d2core_release_metadata(paths)
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    record = locale_manifest["records"][0]
    record["translation_source"] = {
        "provider": "d2core",
        "source_id": "affix:fixture:1:x1",
        "source_record_sha256": "0" * 64,
        "translation_sha256": _sha256_text(record["text"]),
    }
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)
    assert {issue["code"] for issue in _issues(report)} == {"translation_source_hash_mismatch"}

    record["translation_source"] = {
        "provider": "d2core",
        "source_id": "aspect:fixture:2:x1",
        "source_record_sha256": "b" * 64,
        "translation_sha256": _sha256_text(record["text"]),
    }
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)
    assert {issue["code"] for issue in _issues(report)} == {"translation_source_dataset_mismatch"}


def test_d2core_build_runtime_and_conflicts_block_release(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    _enable_d2core_release_metadata(
        paths, d2core_build="72698", runtime_ready=False, conflicts=4, source_quality_ok=False
    )

    report = _check(paths)

    assert {issue["code"] for issue in _issues(report)} == {
        "provider_build_mismatch",
        "runtime_not_ready",
        "source_quality_failed",
        "translation_conflict",
    }


def test_partial_d2core_provider_manifest_is_rejected(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    _enable_d2core_release_metadata(paths)
    source_manifest = json.loads(paths.source_manifest.read_text(encoding="utf-8"))
    del source_manifest["sources"]["d2core"]["files"]["aspect_zhCN.json"]
    _write_json(paths.source_manifest, source_manifest)

    source_hash = _sha256_bytes(paths.source_manifest.read_bytes())
    source_lock = json.loads(paths.source_lock.read_text(encoding="utf-8"))
    source_lock["source_manifest"]["sha256"] = source_hash
    _write_json(paths.source_lock, source_lock)
    locale_manifest = json.loads(paths.locale_manifest.read_text(encoding="utf-8"))
    locale_manifest["source_manifest_sha256"] = source_hash
    _write_json(paths.locale_manifest, locale_manifest)

    report = _check(paths)

    assert any(issue["code"] == "invalid_provider_manifest" for issue in _issues(report))


def test_bad_json_is_machine_readable_input_error(tmp_path: Path, capsys) -> None:
    paths = _make_fixture(tmp_path)
    paths.locale_manifest.write_text("{not-json", encoding="utf-8")

    exit_code = locale_data_check.main([
        "--source-lock",
        str(paths.source_lock),
        "--source-manifest",
        str(paths.source_manifest),
        "--build-version",
        str(paths.build_version),
        "--locale-manifest",
        str(paths.locale_manifest),
    ])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == locale_data_check.EXIT_INPUT_ERROR
    assert report["status"] == "input_error"
    assert report["issues"][0]["code"] == "invalid_json"


def test_argument_errors_are_machine_readable(capsys) -> None:
    exit_code = locale_data_check.main([])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == locale_data_check.EXIT_INPUT_ERROR
    assert report["issues"][0]["code"] == "invalid_arguments"
