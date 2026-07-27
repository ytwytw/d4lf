import hashlib
import json
from typing import TYPE_CHECKING

import pytest

from src.tools.season_data_watch.manifest import WatchInputError
from src.tools.season_data_watch.watch import EXIT_DRIFT, EXIT_OK, check_sources

if TYPE_CHECKING:
    from pathlib import Path

D4DATA_URL = "https://raw.githubusercontent.com/DiabloTools/d4data/master/buildVersion.txt"
COMPANION_URL = (
    "https://raw.githubusercontent.com/josdemmers/Diablo4Companion/master/D4Companion/Data/Affixes.zhCN.json"
)
D2CORE_SITE = "https://www.d2core.com/"
D2CORE_FILE = "https://cloudstorage.d2core.com/data/d4/72698/affix_zhCN.json"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_lock(tmp_path: Path) -> Path:
    value = {
        "schema_version": 1,
        "sources": {
            "d4data": {"role": "canonical_english", "expected_build": "3.1.1.72836", "build_url": D4DATA_URL},
            "diablo4_companion": {
                "role": "supplemental_bilingual",
                "raw_base": "https://raw.githubusercontent.com/josdemmers/Diablo4Companion/master",
                "files": {"D4Companion/Data/Affixes.zhCN.json": {"sha256": _digest(b"companion")}},
            },
            "d2core": {
                "role": "supplemental_licensed",
                "expected_build": "72698",
                "site_url": D2CORE_SITE,
                "files": {"affix_zhCN.json": {"sha256": _digest(b"d2core"), "url": D2CORE_FILE}},
            },
        },
    }
    path = tmp_path / "source-lock.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_check_sources_reports_clean_locked_data(tmp_path: Path) -> None:
    payloads = {
        D4DATA_URL: b"3.1.1.72836\n",
        COMPANION_URL: b"companion",
        D2CORE_SITE: b'const D4_BUILD_VERSION = "72698";',
        D2CORE_FILE: b"d2core",
    }

    report = check_sources(_source_lock(tmp_path), fetch=payloads.__getitem__)

    assert report["ok"] is True
    assert report["exit_code"] == EXIT_OK
    assert len(report["checked_files"]) == 2


def test_check_sources_reports_versions_and_content_drift(tmp_path: Path) -> None:
    payloads = {
        D4DATA_URL: b"3.1.2.73000",
        COMPANION_URL: b"changed",
        D2CORE_SITE: b'const D4_BUILD_VERSION = "73000";',
        D2CORE_FILE: b"changed",
    }

    report = check_sources(_source_lock(tmp_path), fetch=payloads.__getitem__)

    assert report["ok"] is False
    assert report["exit_code"] == EXIT_DRIFT
    assert {issue["code"] for issue in report["issues"]} == {
        "d4data_build_drift",
        "diablo4_companion_file_drift",
        "d2core_build_drift",
        "d2core_file_drift",
    }


def test_check_sources_wraps_d2core_discovery_errors(tmp_path: Path) -> None:
    payloads = {
        D4DATA_URL: b"3.1.1.72836",
        COMPANION_URL: b"companion",
        D2CORE_SITE: b"<html></html>",
        D2CORE_FILE: b"d2core",
    }

    with pytest.raises(WatchInputError, match="discover"):
        check_sources(_source_lock(tmp_path), fetch=payloads.__getitem__)
