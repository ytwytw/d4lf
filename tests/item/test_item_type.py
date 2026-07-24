from src.item.data.item_type import ItemType, is_consumable, is_weapon


def test_skill_point_tome_is_not_equipment() -> None:
    assert is_consumable(ItemType.Tome)
    assert not is_weapon(ItemType.Tome)
