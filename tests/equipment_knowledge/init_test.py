from src.equipment_knowledge import (
    AffixEntry,
    EquipmentCatalog,
    EquipmentEntry,
    EquipmentKnowledgeDialog,
    ItemTypeEntry,
    load_catalog,
)


def test_public_catalog_and_dialog_contract():
    catalog = load_catalog()
    assert isinstance(catalog, EquipmentCatalog)
    assert isinstance(catalog.items[0], EquipmentEntry)
    assert isinstance(catalog.affixes[0], AffixEntry)
    assert isinstance(catalog.item_types[0], ItemTypeEntry)
    assert callable(EquipmentKnowledgeDialog)
