from src.inventory_dump.models import ItemRecord, Location, ScanDocument, ScopeRecord


def test_failed_count_retains_unparsed_and_interrupted_observations() -> None:
    document = ScanDocument("zhCN", "test")
    document.items = [
        ItemRecord(
            Location("inventory", "equipment", str(index), (10, 20)), status=status, capture_complete=status == "parsed"
        )
        for index, status in enumerate(("parsed", "empty", "unparsed", "timeout", "interrupted", "unverified"))
    ]
    assert document.failed_count == 3
    assert document.items[2].location.label == "inventory/equipment/2"


def test_unverified_slots_are_counted_from_scope_coverage_not_items() -> None:
    scope = ScopeRecord("equipped", "talisman", unverified_slots=[{"slot": "seal"}, {"slot": "charm_top"}])
    document = ScanDocument("zhCN", "test", scopes=[scope, ScopeRecord("stash", "1")])
    assert document.unverified_count == 2
    assert document.failed_count == 0
    assert document.schema_version == 2
