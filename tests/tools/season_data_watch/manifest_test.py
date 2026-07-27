import hashlib
import json
from pathlib import Path

import pytest

from src.tools.season_data_watch.manifest import WatchInputError, load_source_lock


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sources": {
            "d4data": {
                "role": "canonical_english",
                "expected_build": "3.1.1.72836",
                "build_url": "https://raw.githubusercontent.com/DiabloTools/d4data/master/buildVersion.txt",
            },
            "diablo4_companion": {
                "role": "supplemental_bilingual",
                "raw_base": "https://raw.githubusercontent.com/josdemmers/Diablo4Companion/master",
                "files": {"D4Companion/Data/Affixes.zhCN.json": {"sha256": _digest(b"companion")}},
            },
            "d2core": {
                "role": "supplemental_licensed",
                "expected_build": "72698",
                "site_url": "https://www.d2core.com/",
                "files": {
                    "affix_zhCN.json": {
                        "sha256": _digest(b"d2core"),
                        "url": "https://cloudstorage.d2core.com/data/d4/72698/affix_zhCN.json",
                    }
                },
            },
        },
    }


def _write_manifest(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "source-lock.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_load_source_lock_builds_safe_file_urls(tmp_path: Path) -> None:
    lock = load_source_lock(_write_manifest(tmp_path, _manifest()))

    assert lock.d4data_build == "3.1.1.72836"
    assert lock.d2core_build == "72698"
    assert lock.companion_files[0].url.endswith("/D4Companion/Data/Affixes.zhCN.json")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update({"schema_version": 2}), "schema_version"),
        (lambda value: value["sources"]["d4data"].update({"role": "source_of_truth"}), "role"),
        (
            lambda value: value["sources"]["diablo4_companion"].update({"raw_base": "https://127.0.0.1/data"}),
            "not allowed",
        ),
        (
            lambda value: value["sources"]["diablo4_companion"].update({
                "files": {"../secret": {"sha256": _digest(b"x")}}
            }),
            "unsafe",
        ),
    ],
)
def test_load_source_lock_rejects_unsafe_or_invalid_metadata(tmp_path: Path, mutate, message: str) -> None:
    value = _manifest()
    mutate(value)

    with pytest.raises(WatchInputError, match=message):
        load_source_lock(_write_manifest(tmp_path, value))


def test_load_source_lock_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "source-lock.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")

    with pytest.raises(WatchInputError, match="not valid"):
        load_source_lock(path)


def test_committed_lock_matches_locale_quality_builds() -> None:
    root = Path(__file__).parents[3]
    lock = load_source_lock(root / "assets/catalog/source-lock.json")
    quality = json.loads((root / "assets/lang/zhCN/quality-report.json").read_text(encoding="utf-8"))

    assert quality["source_builds"] == {"d2core": lock.d2core_build, "d4data": lock.d4data_build}
