import json

import pytest

from src.inventory_dump.exporting import SnapshotWriter
from src.inventory_dump.layout import INVENTORY_PAGES, REQUIRED_EQUIPMENT_SLOTS, TabTarget
from src.inventory_dump.models import ExportFormat, Location, ScanDocument
from src.inventory_dump.navigation import NavigationError, ScanTarget
from src.inventory_dump.reader import ScanCancelledError
from src.inventory_dump.scanner import Scanner


def _dependencies(mocker, tmp_path):
    navigator = mocker.Mock()
    navigator.stash_tabs.return_value = [TabTarget("1", (10, 10), 1), TabTarget("2", (20, 10), 1)]
    navigator.inventory_tabs.return_value = [TabTarget(name, (10, 20), 1) for name in INVENTORY_PAGES]

    def targets(page, *, stash=False):
        return [ScanTarget(Location("stash" if stash else "inventory", page, "r01c01", (1, 1), 1, 1), True, True, True)]

    navigator.grid_targets.side_effect = targets
    navigator.equipped_targets.side_effect = lambda *, talisman=False: [
        ScanTarget(Location("equipped", "talisman" if talisman else "equipment", slot, (3, 3)), True)
        for slot in (["seal"] if talisman else [*sorted(REQUIRED_EQUIPMENT_SLOTS), "weapon_left"])
    ]
    reader = mocker.Mock()

    def read(record, *_args, **_kwargs):
        record.status = "parsed"
        record.raw_tts = ["same item text"]
        record.parsed = {"name": "same"}
        record.capture_complete = True

    reader.read.side_effect = read
    writer = SnapshotWriter(tmp_path / "inventory.json", ExportFormat.JSON)
    return navigator, reader, writer


def test_scan_covers_every_discovered_page_and_equipped_scopes_without_deduplication(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("zhCN", "test"))
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert result.status == "complete"
    assert result.item_count == 17
    assert len({(item["location"]["scope"], item["location"]["page"]) for item in payload["items"]}) == 9
    for item in payload["items"]:
        assert item["favorite"] is None
        assert item["junk"] is None
        if item["location"]["scope"] != "equipped":
            assert item["favorite_evidence"] == [
                {"source": "slot_screenshot_brightness", "verification": "unverified", "value": True}
            ]
            assert item["junk_evidence"] == [
                {"source": "slot_screenshot_template", "verification": "unverified", "value": True}
            ]
        else:
            assert item["favorite_evidence"] == item["junk_evidence"] == []
    reader.close.assert_called_once()
    navigator.restore.assert_called_once()
    navigator.click_pointer.assert_not_called()


def test_cancellation_persists_current_raw_and_lists_every_unvisited_scope(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)

    def interrupt(record, *_args, **_kwargs):
        record.raw_tts = ["half an item"]
        raise ScanCancelledError

    reader.read.side_effect = interrupt
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("zhCN", "test"))
    payload = json.loads(writer.path.read_text(encoding="utf-8"))
    assert result.status == "cancelled"
    assert payload["items"][0]["raw_tts"] == ["half an item"]
    assert payload["items"][0]["status"] == "interrupted"
    assert payload["items"][0]["favorite"] is None
    assert payload["items"][0]["favorite_evidence"][0]["verification"] == "unverified"
    assert (
        next(scope for scope in payload["scopes"] if scope["kind"] == "stash" and scope["page"] == "2")["status"]
        == "not_scanned"
    )
    assert len([scope for scope in payload["scopes"] if scope["kind"] == "inventory"]) == 5
    assert len([scope for scope in payload["scopes"] if scope["kind"] == "equipped"]) == 2
    navigator.inventory_tabs.assert_not_called()


def test_stash_unavailable_still_exports_inventory_but_cannot_claim_complete(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    navigator.stash_tabs.side_effect = NavigationError("stash closed")
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("enUS", "test"))
    assert result.status == "partial"
    assert result.item_count == 15
    assert "stash closed" in result.issues


def test_restore_failure_changes_complete_result_to_partial(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    navigator.restore.side_effect = OSError("window capture failed")
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("enUS", "test"))
    assert result.status == "partial"
    assert "window capture failed" in result.issues[-1]


def test_each_completed_item_is_durable_before_the_next_hover(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    observed = []

    def read(record, *_args, **_kwargs):
        saved = json.loads(writer.path.read_text(encoding="utf-8"))
        observed.append([item["location"]["page"] for item in saved["items"]])
        record.status = "unparsed"
        record.raw_tts = ["unknown raw"]

    reader.read.side_effect = read
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("enUS", "test"))
    # Before hover N, the N-1 previously read items are already in the atomic snapshot.
    assert [len(pages) for pages in observed] == list(range(17))
    assert result.status == "partial"
    assert result.failed_count == 17


def test_unknown_stash_tab_is_reported_without_clicking_or_renumbering(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    unknown = TabTarget("2", (20, 10), 0.9, icon_recognized=False)
    navigator.stash_tabs.return_value = [TabTarget("1", (10, 10), 1), unknown, TabTarget("3", (30, 10), 1)]
    document = ScanDocument("enUS", "test")
    result = Scanner(navigator, reader, writer, lambda _: None).run(document)
    assert result.status == "partial"
    assert next(scope for scope in document.scopes if scope.kind == "stash" and scope.page == "2").status == "failed"
    assert any(item.location.scope == "stash" and item.location.page == "3" for item in document.items)
    assert not any(call.args[0] == unknown for call in navigator.select_tab.call_args_list)


def test_missed_equipment_frames_do_not_silently_claim_complete_coverage(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    navigator.equipped_targets.side_effect = lambda *, talisman=False: [
        ScanTarget(
            Location("equipped", "talisman" if talisman else "equipment", "seal" if talisman else "head", (3, 3)), True
        )
    ]
    document = ScanDocument("enUS", "test")
    result = Scanner(navigator, reader, writer, lambda _: None).run(document)
    assert result.status == "partial"
    equipment = next(scope for scope in document.scopes if scope.kind == "equipped" and scope.page == "equipment")
    assert equipment.status == "partial"
    assert "chest" in equipment.errors[0]
    assert "weapon slots" in equipment.errors[0]
    assert any(item.location.slot == "head" for item in document.items)


def test_empty_ambient_observations_count_as_empty_slots_without_fake_items(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)

    def read_empty(record, *_args, **_kwargs):
        record.status = "empty"
        record.raw_tts = ["Höpe | 70 (133)"]

    reader.read.side_effect = read_empty
    document = ScanDocument("zhCN", "test")
    result = Scanner(navigator, reader, writer, lambda _: None).run(document)
    assert result.item_count == 0
    assert result.failed_count == 0
    assert sum(scope.empty_slots for scope in document.scopes) == 17
    assert all(scope.observed_items == 0 for scope in document.scopes)


def test_complete_raw_export_succeeds_even_when_legacy_unique_mapping_fails(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)

    def capture_unknown(record, *_args, **_kwargs):
        record.status = "parse_error"
        record.capture_complete = True
        record.raw_tts = ["李奥瑞克的王冠", "先祖暗金头盔", "900 物品强度", "鼠标右键"]
        record.error = "Unrecognized unique"

    reader.read.side_effect = capture_unknown
    document = ScanDocument("zhCN", "test")
    result = Scanner(navigator, reader, writer, lambda _: None).run(document)
    assert result.status == "complete"
    assert result.failed_count == 0
    assert result.unparsed_count == 17
    assert all(scope.status == "complete" for scope in document.scopes if scope.page != "all")
    assert document.items[0].status == "parse_error"
    assert document.items[0].error == "Unrecognized unique"


def test_truncated_capture_still_reports_partial_even_if_a_parser_returned_an_item(mocker, tmp_path) -> None:
    navigator, reader, writer = _dependencies(mocker, tmp_path)

    def capture_truncated(record, *_args, **_kwargs):
        record.status = "parsed"
        record.capture_complete = True
        record.truncated = True
        record.raw_tts = ["incomplete text"]

    reader.read.side_effect = capture_truncated
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("enUS", "test"))
    assert result.status == "partial"
    assert result.failed_count == 17


def _evidence_scan(mocker, tmp_path, outcomes: dict[str, str], grid=(True, False, False), settled=True):
    """``outcomes`` maps a location label to the reader result; others read as items or settled-empty."""
    navigator, reader, writer = _dependencies(mocker, tmp_path)
    navigator.stash_tabs.return_value = [TabTarget("1", (10, 10), 1)]
    navigator.grid_targets.side_effect = lambda page, *, stash=False: [
        ScanTarget(
            Location("stash" if stash else "inventory", page, f"r01c{i + 1:02d}", (i, 1), 1, i + 1),
            value if settled or value else None,
            occupancy={"verification": "unverified", "value": value, "icons_settled": settled},
        )
        for i, value in enumerate(grid)
    ]
    navigator.equipped_targets.side_effect = lambda *, talisman=False: [
        ScanTarget(Location("equipped", "talisman" if talisman else "equipment", slot, (3, 3)), None)
        for slot in (["charm_top", "seal"] if talisman else [*sorted(REQUIRED_EQUIPMENT_SLOTS), "weapon_left"])
    ]

    def read(record, *_args, expected_occupied=True):
        record.attempts = 2
        outcome = outcomes.get(record.location.label)
        if outcome == "cancel":
            raise ScanCancelledError
        outcome = outcome or {
            False: "empty",
            None: "unverified" if record.location.scope != "equipped" else "parsed",
        }.get(expected_occupied, "parsed")
        record.status, record.capture_complete = outcome, outcome == "parsed"
        text = "神符" if record.location.slot == "charm_top" else "电池充电中"  # charm: its own label only
        record.raw_events = [{"sequence": 9, "text": text, "received_at": 1.0, "attempt": 1}]

    reader.read.side_effect = read
    saves = mocker.spy(writer, "save")
    result = Scanner(navigator, reader, writer, lambda _: None).run(ScanDocument("zhCN", "test"))
    payload = json.loads(writer.path.read_text(encoding="utf-8"))
    return result, {(scope["kind"], scope["page"]): scope for scope in payload["scopes"]}, payload, saves


def test_confirmed_empty_slots_keep_evidence_without_item_records(mocker, tmp_path) -> None:
    result, scopes, payload, _ = _evidence_scan(mocker, tmp_path, {})
    assert (result.status, result.unverified_count, result.item_count) == ("complete", 0, 6 + 9 + 2)
    stash = scopes["stash", "1"]
    assert (stash["status"], stash["observed_items"], stash["empty_slots"], stash["occupancy_settled"]) == (
        "complete",
        1,
        2,
        True,
    )
    entry = stash["empty_slot_evidence"][0]
    assert (entry["slot"], entry["verification"], entry["attempts"]) == (
        "r01c02",
        "settled_visual_empty_and_no_item_tts",
        2,
    )
    assert entry["visual_occupancy"]["value"] is False
    assert entry["raw_events"][0]["text"] == "电池充电中"
    assert not any(item["location"]["slot"] in {"r01c02", "r01c03"} for item in payload["items"])


@pytest.mark.parametrize("settled", [True, False])
def test_unknown_occupancy_is_listed_as_unverified_and_never_claims_complete(mocker, tmp_path, settled) -> None:
    outcomes = {"equipped/talisman/seal": "unverified", "equipped/talisman/charm_top": "unverified"}
    result, scopes, payload, _ = _evidence_scan(mocker, tmp_path, outcomes, settled=settled)
    grid_unknown = 0 if settled else 2 * 6
    assert (result.status, result.failed_count, result.unverified_count) == ("partial", 0, 2 + grid_unknown)
    talisman = scopes["equipped", "talisman"]
    assert (talisman["status"], talisman["empty_slots"], talisman["empty_slot_evidence"]) == ("unverified", 0, [])
    # Label-only and silent equipped slots stay unknown, with their raw events kept for inspection.
    unknown = [(entry["slot"], entry["raw_events"][0]["text"]) for entry in talisman["unverified_slots"]]
    assert unknown == [("charm_top", "神符"), ("seal", "电池充电中")]
    assert scopes["stash", "1"]["status"] == ("complete" if settled else "unverified")
    assert scopes["stash", "1"]["occupancy_settled"] is settled
    assert not any(item["status"] in {"empty", "unverified"} for item in payload["items"])
    assert any("seal" in issue for issue in result.issues)


def test_one_write_per_item_and_empty_evidence_rides_with_the_next_write(mocker, tmp_path) -> None:
    result, _, _, saves = _evidence_scan(mocker, tmp_path, {}, grid=(False, False, True))
    scanned_scopes = 1 + len(INVENTORY_PAGES) + 2
    # start + stash discovery + (scanning + end) per scope + one per item (6 grid + 9 equipped + 2 talisman) + final.
    assert saves.call_count == 1 + 1 + 2 * scanned_scopes + 17 + 1
    assert result.item_count == 17


def test_cancel_after_unsaved_empty_slots_still_persists_their_evidence(mocker, tmp_path) -> None:
    result, scopes, payload, _ = _evidence_scan(
        mocker, tmp_path, {"stash/1/r01c03": "cancel"}, grid=(False, False, True)
    )
    assert result.status == "cancelled"
    assert [entry["slot"] for entry in scopes["stash", "1"]["empty_slot_evidence"]] == ["r01c01", "r01c02"]
    assert [(item["location"]["slot"], item["status"]) for item in payload["items"]] == [("r01c03", "interrupted")]
