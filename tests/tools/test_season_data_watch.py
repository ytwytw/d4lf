from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, cast

import pytest

from src.tools import d2core_data, season_data_watch

if TYPE_CHECKING:
    from pathlib import Path


def _report_entries(report: dict[str, object], key: str) -> list[dict[str, object]]:
    entries = report[key]
    assert isinstance(entries, list)
    assert all(isinstance(entry, dict) for entry in entries)
    return cast("list[dict[str, object]]", entries)


def _manifest(tmp_path: Path, source_file: bytes = b"source") -> tuple[Path, str]:
    relative_path = "D4Companion/Data/Affixes.zhCN.json"
    path = tmp_path / "source-manifest.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "build_version": "3.1.0.72592",
            "sources": {
                "diablo4_companion": {
                    "files": {relative_path: {"records": 1, "sha256": hashlib.sha256(source_file).hexdigest()}}
                }
            },
            "records": [],
        }),
        encoding="utf-8",
    )
    return path, relative_path


def _add_d2core_source(path: Path, source_file: bytes = b"d2core", build_version: str = "72698") -> dict[str, bytes]:
    keys = {(spec.name, locale) for spec in d2core_data.DATASET_SPECS for locale in d2core_data.LOCALES}
    payloads = {key: source_file + d2core_data.snapshot_filename(*key).encode() for key in keys}
    records = {key: ({},) * d2core_data.MINIMUM_RECORD_COUNTS[key[0]] for key in keys}
    urls = {key: d2core_data.dataset_url(build_version, *key) for key in keys}
    d2core_manifest = d2core_data.build_manifest(
        build_version=build_version,
        payloads=payloads,
        records=records,
        urls=urls,
        build_version_source={"kind": "pinned"},
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    source = d2core_manifest["source"]
    assert isinstance(source, dict)
    typed_source = cast("dict[str, object]", source)
    typed_source["site_url"] = "https://d2.invalid/"
    manifest["sources"]["d2core"] = d2core_manifest
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return {urls[key]: payload for key, payload in payloads.items()}


def test_watch_passes_when_build_and_source_hashes_match(tmp_path: Path) -> None:
    source_file = b"source"
    manifest, relative_path = _manifest(tmp_path, source_file)
    responses = {"build": b"3.1.0.72592\n", f"raw/{relative_path}": source_file}

    report = season_data_watch.check_sources(
        source_manifest=manifest, d4data_build_url="build", companion_raw_base="raw", fetch=responses.__getitem__
    )

    assert report["exit_code"] == season_data_watch.EXIT_OK
    assert report["issues"] == []
    assert report["checked_files"] == [{"path": relative_path, "sha256": hashlib.sha256(source_file).hexdigest()}]


def test_watch_reports_build_and_file_drift_deterministically(tmp_path: Path) -> None:
    manifest, relative_path = _manifest(tmp_path)
    responses = {"build": b"3.1.1.99999\n", f"raw/{relative_path}": b"changed"}

    report = season_data_watch.check_sources(
        source_manifest=manifest, d4data_build_url="build", companion_raw_base="raw", fetch=responses.__getitem__
    )

    assert report["exit_code"] == season_data_watch.EXIT_DRIFT
    assert [issue["code"] for issue in _report_entries(report, "issues")] == ["build_drift", "file_drift"]


def test_watch_rejects_invalid_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "source-manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(season_data_watch.WatchInputError, match="build_version"):
        season_data_watch.check_sources(source_manifest=manifest, fetch=lambda _url: b"")


def test_watch_checks_d2core_build_and_locked_file_hashes(tmp_path: Path) -> None:
    companion_source = b"source"
    d2core_source = b"d2core"
    manifest, relative_path = _manifest(tmp_path, companion_source)
    d2core_responses = _add_d2core_source(manifest, d2core_source)
    responses = {
        "build": b"3.1.0.72592\n",
        f"raw/{relative_path}": companion_source,
        "https://d2.invalid/": b'<script src="/assets/app.js"></script>',
        "https://d2.invalid/assets/app.js": b'D4_BUILD_VERSION="72698"',
        **d2core_responses,
    }

    report = season_data_watch.check_sources(
        source_manifest=manifest, d4data_build_url="build", companion_raw_base="raw", fetch=responses.__getitem__
    )

    assert report["exit_code"] == season_data_watch.EXIT_OK
    assert report["upstream_d2core_build"] == "72698"
    assert _report_entries(report, "checked_files")[-1] == {
        "path": "d2core/uniqueItem_zhCN.json",
        "sha256": hashlib.sha256(d2core_responses[d2core_data.dataset_url("72698", "uniqueItem", "zhCN")]).hexdigest(),
    }


def test_watch_reports_d2core_build_and_file_drift(tmp_path: Path) -> None:
    manifest, relative_path = _manifest(tmp_path)
    d2core_responses = _add_d2core_source(manifest)
    responses = {
        "build": b"3.1.0.72592\n",
        f"raw/{relative_path}": b"source",
        "https://d2.invalid/": b'<script src="/assets/app.js"></script>',
        "https://d2.invalid/assets/app.js": b'D4_BUILD_VERSION="99999"',
        **d2core_responses,
    }
    responses[d2core_data.dataset_url("72698", "affix", "enUS")] = b"changed"

    report = season_data_watch.check_sources(
        source_manifest=manifest, d4data_build_url="build", companion_raw_base="raw", fetch=responses.__getitem__
    )

    assert [issue["code"] for issue in _report_entries(report, "issues")] == ["d2core_build_drift", "d2core_file_drift"]


def test_watch_rejects_partial_d2core_manifest(tmp_path: Path) -> None:
    manifest, _ = _manifest(tmp_path)
    _add_d2core_source(manifest)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    del value["sources"]["d2core"]["files"]["aspect_zhCN.json"]
    manifest.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(season_data_watch.WatchInputError, match="files do not match"):
        season_data_watch.check_sources(source_manifest=manifest, fetch=lambda _url: b"")
