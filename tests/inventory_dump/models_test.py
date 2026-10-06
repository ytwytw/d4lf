from src.inventory_dump.models import ItemRecord, Location, ScanDocument


def test_failed_count_retains_unparsed_and_interrupted_observations() -> None:
    document = ScanDocument("zhCN", "test")
    document.items = [
        ItemRecord(
            Location("inventory", "equipment", str(index), (10, 20)), status=status, capture_complete=status == "parsed"
        )
        for index, status in enumerate(("parsed", "empty", "unparsed", "timeout", "interrupted"))
    ]
    assert document.failed_count == 3
    assert document.items[2].location.label == "inventory/equipment/2"
