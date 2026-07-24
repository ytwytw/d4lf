from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, cast

import pytest

from src.tools import d2core_data

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

BUILD_VERSION = "72698"
SITE_URL = "https://fixtures.example/"
STATIC_ROOT = "https://static.fixtures.example/data/d4"


def _json_bytes(value: object, *, bom: bool = False) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return (b"\xef\xbb\xbf" if bom else b"") + payload


@pytest.fixture
def payloads(monkeypatch) -> dict[d2core_data.SnapshotKey, bytes]:
    monkeypatch.setattr(d2core_data, "MINIMUM_RECORD_COUNTS", {spec.name: 1 for spec in d2core_data.DATASET_SPECS})
    return {
        ("affix", "enUS"): _json_bytes(
            {
                "affix": [
                    {"key": "S04_Armor", "id": 10, "descTpl": "Armor"},
                    {"key": "Duplicate", "id": 11, "descTpl": "Damage"},
                    {"key": "Duplicate", "id": 11, "descTpl": "Damage"},
                ],
                "attributeFormulas": {},
            },
            bom=True,
        ),
        ("affix", "zhCN"): _json_bytes(
            {
                "affix": [
                    {"key": "Duplicate", "id": 11, "descTpl": "伤害"},
                    {"key": "S04_Armor", "id": 10, "descTpl": "护甲"},
                    {"key": "Duplicate", "id": 11, "descTpl": "伤害"},
                ],
                "attributeFormulas": {},
            },
            bom=True,
        ),
        ("aspect", "enUS"): _json_bytes([{"key": "Affix_legendary_sorc_001", "id": 20, "name": "Aspect of Focus"}]),
        ("aspect", "zhCN"): _json_bytes([{"key": "Affix_legendary_sorc_001", "id": 20, "name": "专注之威能"}]),
        ("uniqueItem", "enUS"): _json_bytes([{"key": "Pants_Unique_Sorc_101", "id": 30, "name": "Axial Conduit"}]),
        ("uniqueItem", "zhCN"): _json_bytes([{"key": "Pants_Unique_Sorc_101", "id": 30, "name": "枢轴导体"}]),
        ("talisman", "enUS"): _json_bytes({
            "charm": [{"key": "Charm_Test", "id": 40, "name": "Test Charm"}],
            "seal": [{"key": "Seal_Test", "id": 41, "name": "Test Seal"}],
            "itemSets": {"Talisman_Test": {"id": 42, "name": "Test Set"}},
            "affixes": {
                "charm": [{"key": "Charm_Affix", "id": 43, "descTpl": "+[{VALUE}] Charm Damage"}],
                "seal": [{"key": "Seal_Affix", "id": 44, "descTpl": "+[{VALUE}] Seal Damage"}],
            },
        }),
        ("talisman", "zhCN"): _json_bytes({
            "charm": [{"key": "Charm_Test", "id": 40, "name": "测试神符"}],
            "seal": [{"key": "Seal_Test", "id": 41, "name": "测试封印"}],
            "itemSets": {"Talisman_Test": {"id": 42, "name": "测试套装"}},
            "affixes": {
                "charm": [{"key": "Charm_Affix", "id": 43, "descTpl": "+[{VALUE}] 神符伤害"}],
                "seal": [{"key": "Seal_Affix", "id": 44, "descTpl": "+[{VALUE}] 封印伤害"}],
            },
        }),
    }


def _responses(payloads: dict[d2core_data.SnapshotKey, bytes]) -> dict[str, bytes]:
    return {
        d2core_data.dataset_url(BUILD_VERSION, *key, static_data_root=STATIC_ROOT): payload
        for key, payload in payloads.items()
    }


def _recording_fetch(responses: dict[str, bytes]) -> tuple[Callable[[str], bytes], list[str]]:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return responses[url]

    return fetch, calls


def test_pure_parsers_extract_scripts_build_and_bom_json() -> None:
    html = b"<html><script src='/assets/vendor.js'></script><script src='/assets/index-ABC.js'></script></html>"
    bundle = b'const D4_BUILD_VERSION="72698",D4_PTR_BUILD_VERSION="70000";'
    payload = b'\xef\xbb\xbf[{"key":"A","id":1,"name":"\xe5\x90\x8d\xe7\xa7\xb0"}]'

    assert d2core_data.extract_script_sources(html) == ("/assets/vendor.js", "/assets/index-ABC.js")
    assert d2core_data.extract_build_version(bundle) == BUILD_VERSION
    assert d2core_data.validate_dataset_payload("aspect", "zhCN", payload)[0]["name"] == "名称"


def test_validate_locale_pair_compares_key_id_multisets(payloads: dict[d2core_data.SnapshotKey, bytes]) -> None:
    en_us = d2core_data.validate_dataset_payload("affix", "enUS", payloads["affix", "enUS"])
    zh_cn = d2core_data.validate_dataset_payload("affix", "zhCN", payloads["affix", "zhCN"])
    d2core_data.validate_locale_pair("affix", en_us, zh_cn)

    mismatched = [*zh_cn]
    mismatched[-1] = {**mismatched[-1], "id": 12}
    with pytest.raises(d2core_data.PairValidationError, match=r"missing_from_zhCN=.*'id': 11"):
        d2core_data.validate_locale_pair("affix", en_us, mismatched)


def test_talisman_payload_flattens_all_current_equipment_sections(
    payloads: dict[d2core_data.SnapshotKey, bytes],
) -> None:
    records = d2core_data.validate_dataset_payload("talisman", "enUS", payloads["talisman", "enUS"])

    assert {record["section"] for record in records} == {"affixes.charm", "affixes.seal", "charm", "itemSets", "seal"}
    item_set = next(record for record in records if record["section"] == "itemSets")
    assert item_set["key"] == "itemSets:Talisman_Test"
    assert item_set["sourceKey"] == "Talisman_Test"
    assert item_set["text"] == "Test Set"


@pytest.mark.parametrize(
    ("dataset", "locale", "value", "message"),
    [
        ("affix", "enUS", [], "expected object root"),
        ("aspect", "enUS", [{"key": "A", "id": True, "name": "Aspect"}], "non-negative integer"),
        ("uniqueItem", "zhCN", [{"key": "A", "id": 1}], "name"),
        ("talisman", "enUS", {"charm": [], "seal": [], "itemSets": {}, "affixes": {}}, "affixes.charm"),
    ],
)
def test_dataset_schema_validation_rejects_invalid_shapes(
    dataset: str, locale: str, value: object, message: str
) -> None:
    with pytest.raises(d2core_data.SchemaValidationError, match=message):
        d2core_data.validate_dataset_payload(dataset, locale, _json_bytes(value))


def test_fetch_pinned_snapshot_is_deterministic_and_round_trips(
    tmp_path: Path, payloads: dict[d2core_data.SnapshotKey, bytes]
) -> None:
    responses = _responses(payloads)
    first_fetch, first_calls = _recording_fetch(responses)
    second_fetch, _ = _recording_fetch(responses)

    first = d2core_data.fetch_snapshot(
        tmp_path / "first",
        build_version=BUILD_VERSION,
        fetch=first_fetch,
        site_url=SITE_URL,
        static_data_root=STATIC_ROOT,
    )
    second = d2core_data.fetch_snapshot(
        tmp_path / "second",
        build_version=BUILD_VERSION,
        fetch=second_fetch,
        site_url=SITE_URL,
        static_data_root=STATIC_ROOT,
    )

    assert first.build_version == BUILD_VERSION
    assert SITE_URL not in first_calls
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    assert first.payloads["affix", "enUS"].startswith(b"\xef\xbb\xbf")
    assert first.manifest["authorization"] == {
        "public_redistribution": "documented",
        "reference": "docs/third-party-data.md#d2core",
    }
    files = cast("dict[str, object]", first.manifest["files"])
    affix_metadata = cast("dict[str, object]", files["affix_enUS.json"])
    assert affix_metadata["sha256"] == hashlib.sha256(payloads["affix", "enUS"]).hexdigest()
    assert affix_metadata["records"] == 3
    assert first.manifest["build_version_source"] == {"kind": "pinned"}


def test_fetch_snapshot_discovers_build_from_same_origin_index_bundle(
    tmp_path: Path, payloads: dict[d2core_data.SnapshotKey, bytes]
) -> None:
    bundle_url = f"{SITE_URL}assets/index-ABC.js"
    responses = {
        SITE_URL: b"<script src='/third-party.js'></script><script src='/assets/index-ABC.js'></script>",
        bundle_url: b'const D4_BUILD_VERSION="72698";',
        **_responses(payloads),
    }
    fetch, calls = _recording_fetch(responses)

    snapshot = d2core_data.fetch_snapshot(
        tmp_path / "snapshot", fetch=fetch, site_url=SITE_URL, static_data_root=STATIC_ROOT
    )

    assert calls[:2] == [SITE_URL, bundle_url]
    assert f"{SITE_URL}third-party.js" not in calls
    assert snapshot.manifest["build_version_source"] == {"kind": "discovered", "url": bundle_url}


def test_load_snapshot_rejects_tampered_payload(tmp_path: Path, payloads: dict[d2core_data.SnapshotKey, bytes]) -> None:
    fetch, _ = _recording_fetch(_responses(payloads))
    output_dir = tmp_path / "snapshot"
    d2core_data.fetch_snapshot(
        output_dir, build_version=BUILD_VERSION, fetch=fetch, site_url=SITE_URL, static_data_root=STATIC_ROOT
    )
    (output_dir / "aspect_zhCN.json").write_bytes(b"[]")

    with pytest.raises(d2core_data.SnapshotValidationError, match="sha256 mismatch: aspect_zhCN.json"):
        d2core_data.load_snapshot(output_dir)


def test_fetch_does_not_write_partial_snapshot_when_locale_pair_is_invalid(
    tmp_path: Path, payloads: dict[d2core_data.SnapshotKey, bytes]
) -> None:
    invalid_payloads = dict(payloads)
    invalid_payloads["aspect", "zhCN"] = _json_bytes([
        {"key": "Affix_legendary_sorc_001", "id": 21, "name": "专注之威能"}
    ])
    fetch, _ = _recording_fetch(_responses(invalid_payloads))
    output_dir = tmp_path / "invalid"

    with pytest.raises(d2core_data.PairValidationError, match="aspect"):
        d2core_data.fetch_snapshot(
            output_dir, build_version=BUILD_VERSION, fetch=fetch, site_url=SITE_URL, static_data_root=STATIC_ROOT
        )

    assert not output_dir.exists()


def test_load_snapshot_rejects_manifest_file_set_with_path_traversal(
    tmp_path: Path, payloads: dict[d2core_data.SnapshotKey, bytes]
) -> None:
    fetch, _ = _recording_fetch(_responses(payloads))
    output_dir = tmp_path / "snapshot"
    snapshot = d2core_data.fetch_snapshot(
        output_dir, build_version=BUILD_VERSION, fetch=fetch, site_url=SITE_URL, static_data_root=STATIC_ROOT
    )
    manifest = json.loads(snapshot.manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["../affix_enUS.json"] = manifest["files"].pop("affix_enUS.json")
    snapshot.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(d2core_data.SnapshotValidationError, match="files do not match"):
        d2core_data.load_snapshot(output_dir)


def test_strict_json_rejects_duplicate_keys_and_non_standard_constants() -> None:
    with pytest.raises(d2core_data.SchemaValidationError, match="duplicate object key"):
        d2core_data.parse_json_bytes(b'{"key":1,"key":2}')
    with pytest.raises(d2core_data.SchemaValidationError, match="non-standard JSON value"):
        d2core_data.parse_json_bytes(b'{"value":NaN}')


def test_snapshot_policy_rejects_eight_matching_empty_files_without_writing(tmp_path: Path) -> None:
    empty_values = {
        "affix": {"affix": []},
        "aspect": [],
        "uniqueItem": [],
        "talisman": {"charm": [], "seal": [], "itemSets": {}, "affixes": {"charm": [], "seal": []}},
    }
    payloads = {
        (spec.name, locale): _json_bytes(empty_values[spec.name])
        for spec in d2core_data.DATASET_SPECS
        for locale in d2core_data.LOCALES
    }
    records = dict.fromkeys(payloads, ())
    urls = {key: d2core_data.dataset_url(BUILD_VERSION, *key, static_data_root=STATIC_ROOT) for key in payloads}
    manifest = d2core_data.build_manifest(
        build_version=BUILD_VERSION,
        payloads=payloads,
        records=records,
        urls=urls,
        build_version_source={"kind": "pinned"},
        site_url=SITE_URL,
        static_data_root=STATIC_ROOT,
    )
    output_dir = tmp_path / "empty"

    with pytest.raises(d2core_data.SnapshotValidationError, match="record safety floor"):
        d2core_data.write_snapshot(output_dir, manifest, payloads)

    assert not output_dir.exists()
