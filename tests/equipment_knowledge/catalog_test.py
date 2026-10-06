import hashlib
import json
import subprocess
from shutil import copyfile, which

import pytest

from src.equipment_knowledge import EquipmentCatalog, load_catalog
from src.equipment_knowledge.catalog import catalog_path
from src.tools.equipment_knowledge_snapshot import write_snapshot


def test_snapshot_contains_paired_equipment_and_keeps_versions_separate():
    catalog = load_catalog()
    assert catalog.game_version == "3.2.1.73552"
    assert len(catalog.items) == 380
    assert len(catalog.affixes) == 1070
    assert all(item.raw_zh and item.raw_en["id"] == item.raw_zh["id"] for item in catalog.items)
    native = next(source for source in catalog.data.sources if "upstream_metadata" in source)
    metadata = native["upstream_metadata"]
    assert isinstance(metadata, dict)
    assert metadata["d4lootbench_build"] == "LootBenchDataExtract build 3.1.0.72592"
    assert native["rejected_keys"] == []
    bundled = catalog_path().parent / "sources/native-affixes.json"
    assert native["sha256_scope"] == "original downloaded source bytes"
    assert native["bundled_sha256"] == hashlib.sha256(bundled.read_bytes()).hexdigest()
    d2core = [source for source in catalog.data.sources if source.get("provider") == "D2Core"]
    assert len(d2core) == 4
    for source in d2core:
        assert source["public_redistribution"] == "verified"
        assert source["public_redistribution_basis"] == "project_user_statement"
        reference = source["public_redistribution_evidence"]
        assert isinstance(reference, str)
        evidence_path = catalog_path().parents[2] / reference.split("#")[0]
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert evidence["confirmation_date"] == "2026-10-05"
        assert evidence["independent_contract_review"] is False
        assert evidence["is_d2core_public_license"] is False
        assert evidence["files"][source["file"]]["sha256"] == source["sha256"]


def test_verified_native_mappings_and_unknowns():
    catalog = load_catalog()
    assert catalog.resolve_unique("fists_of_fate") == (186283,)
    assert catalog.resolve_unique("命运之拳") == (186283,)
    assert catalog.resolve_item_type("boots") == (446832,)
    assert 583654 in catalog.resolve_affix("willpower")
    assert 577173 in catalog.resolve_affix("maximum_life")
    assert catalog.resolve_affix("to_hellfire_skills") == (2534852,)
    assert catalog.resolve_unique("made_up_item") == ()
    assert catalog.resolve_affix("made_up_affix") == ()
    assert catalog.resolve_item_type("made_up_type") == ()


def test_chinese_name_collision_is_not_silently_resolved():
    catalog = load_catalog()
    first, second = catalog.items[:2]
    assert first.name_zh is not None
    collision = second.model_copy(update={"name_zh": first.name_zh})
    data = catalog.data.model_copy(update={"items": (first, collision)})
    assert EquipmentCatalog(data).resolve_unique(first.name_zh) == ()
    assert EquipmentCatalog(data).resolve_unique(first.canonical_name) == (first.sno_id,)


def test_corrupt_snapshot_part_is_rejected(tmp_path):
    payload = json.loads(catalog_path().read_text(encoding="utf-8"))
    first = payload["parts"][0]
    (tmp_path / first["path"]).write_text("{}", encoding="utf-8")
    index = tmp_path / "catalog.json"
    index.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_catalog(index)


def test_windows_git_checkout_preserves_manifest_locked_json_bytes(tmp_path):
    git = which("git")
    if git is None:
        pytest.skip("Git is required to verify checkout line-ending behavior")
    source = catalog_path()
    catalog = load_catalog()
    data = catalog.data.model_copy(update={"items": catalog.items[:1], "affixes": catalog.affixes[:1]})
    output = tmp_path / "assets/equipment_knowledge/catalog-73552.json"
    write_snapshot(data, output)
    bundled = output.parent / "sources/native-affixes.json"
    bundled.parent.mkdir()
    copyfile(source.parent / "sources/native-affixes.json", bundled)
    copyfile(source.parents[2] / ".gitattributes", tmp_path / ".gitattributes")
    before = {path.relative_to(tmp_path): path.read_bytes() for path in output.parent.rglob("*.json")}
    for args in (("init", "--quiet"), ("add", ".")):
        subprocess.run([git, "-c", "core.autocrlf=true", *args], cwd=tmp_path, check=True, capture_output=True)
    # Restoring from Git's index exercises smudge conversion as on Windows checkout.
    for path in before:
        (tmp_path / path).unlink()
    subprocess.run(
        [git, "-c", "core.autocrlf=true", "checkout-index", "--all"], cwd=tmp_path, check=True, capture_output=True
    )
    assert all((tmp_path / path).read_bytes() == content for path, content in before.items())
    assert load_catalog(output).data == data
