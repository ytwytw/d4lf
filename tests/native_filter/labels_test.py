from src.equipment_knowledge import load_catalog
from src.native_filter import Condition, ConditionKind
from src.native_filter.labels import catalog_labels, describe_condition


def test_known_labels_resolve_and_unknown_identity_stays_visible():
    names = catalog_labels(load_catalog())
    assert "未知" not in describe_condition(Condition(ConditionKind.ITEM_TYPES, sno_ids=(446832,)), names)
    assert "未知 ID 4294967294" in describe_condition(Condition(ConditionKind.ITEM_TYPES, sno_ids=(4294967294,)), names)
    rarity = describe_condition(Condition(ConditionKind.RARITY, mask=40), names)
    assert "传奇" in rarity
    assert "神话" in rarity
    assert "mask" not in rarity
