import hashlib
import json
from typing import TYPE_CHECKING

import pytest

from src.tools.build_equipment_knowledge import d2core_source, pair_rows, redistribution_notice

if TYPE_CHECKING:
    from src.type_aliases import JsonObject


def test_duplicate_affixes_are_paired_by_context_not_list_order():
    a: JsonObject = {"key": "same", "id": 1, "charType": ["Druid"], "itemType": ["Boots"]}
    b: JsonObject = {"key": "same", "id": 1, "charType": ["Rogue"], "itemType": ["Gloves"]}
    pairs = pair_rows([a, b], [{**b, "desc": "中文乙"}, {**a, "desc": "中文甲"}])
    assert pairs[0][1]["desc"] == "中文甲"
    assert pairs[1][1]["desc"] == "中文乙"
    with pytest.raises(ValueError, match="Missing matching Chinese"):
        pair_rows([a, b], [a])


@pytest.fixture
def permission_root(tmp_path):
    path = tmp_path / "assets/equipment_knowledge/sources/d2core-redistribution-permission-20261005.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "provider": "D2Core",
            "confirmation_type": "project_user_statement",
            "public_redistribution": "verified",
            "files": {
                "affix_enUS.json": {
                    "sha256": hashlib.sha256(b"known source bytes").hexdigest(),
                    "build": "73552",
                    "url": "https://cloudstorage.d2core.com/data/d4/73552/affix_enUS.json?env=prod&v=8",
                }
            },
        }),
        encoding="utf-8",
    )
    return tmp_path


def test_matching_source_keeps_user_confirmation_evidence(permission_root):
    source = d2core_source(permission_root, "affix_enUS.json", b"known source bytes")
    assert source["public_redistribution"] == "verified"
    assert source["public_redistribution_basis"] == "project_user_statement"
    assert source["public_redistribution_evidence"] == (
        "assets/equipment_knowledge/sources/d2core-redistribution-permission-20261005.json#/files/affix_enUS.json"
    )
    assert "用户已确认的来源哈希范围" in redistribution_notice([source])


@pytest.mark.parametrize(
    ("filename", "content"), [("affix_enUS.json", b"changed source bytes"), ("unknown.json", b"known source bytes")]
)
def test_unknown_source_does_not_inherit_confirmed_permission(permission_root, filename, content):
    source = d2core_source(permission_root, filename, content)
    verified = d2core_source(permission_root, "affix_enUS.json", b"known source bytes")
    assert source["public_redistribution"] == "unverified"
    assert "public_redistribution_evidence" not in source
    assert "未全部确认" in redistribution_notice([verified, source])


def test_missing_permission_record_keeps_source_unverified(tmp_path):
    source = d2core_source(tmp_path, "affix_enUS.json", b"known source bytes")
    assert source["public_redistribution"] == "unverified"
    assert "public_redistribution_evidence" not in source
    assert "未全部确认" in redistribution_notice([source])
