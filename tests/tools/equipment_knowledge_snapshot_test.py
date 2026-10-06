import json

import pytest

from src.equipment_knowledge import load_catalog
from src.equipment_knowledge.catalog import catalog_path
from src.tools.equipment_knowledge_snapshot import write_snapshot


def test_split_snapshot_roundtrip_preserves_evidence_and_size_budget(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "catalog.json"
    write_snapshot(catalog.data, path)
    assert load_catalog(path).data == catalog.data
    for part in tmp_path.glob("*.json"):
        content = part.read_bytes()
        assert len(content) <= 450_000
        formatted = json.dumps(json.loads(content), ensure_ascii=False, indent=4, sort_keys=True) + "\n"
        assert content == formatted.encode("utf-8")


def test_bundled_snapshot_is_unchanged_by_json_hook_formatting():
    catalog = load_catalog()
    for path in catalog_path().parent.glob("*.json"):
        content = path.read_bytes()
        assert len(content) <= 450_000
        formatted = json.dumps(json.loads(content), ensure_ascii=False, indent=4, sort_keys=True) + "\n"
        assert content == formatted.encode("utf-8")
    assert len(catalog.items) == 380
    assert len(catalog.affixes) == 1070


def test_oversized_single_record_is_rejected(tmp_path):
    catalog = load_catalog()
    item = catalog.items[0].model_copy(update={"raw_en": {"large": "x" * 450_001}})
    data = catalog.data.model_copy(update={"items": (item,)})
    with pytest.raises(ValueError, match="single knowledge record"):
        write_snapshot(data, tmp_path / "catalog.json")
