"""Read every observed inventory scope, with durable progress and cooperative cancellation."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src import __version__
from src.diagnostics import GameInputCancelledError
from src.inventory_dump.exporting import SnapshotWriter
from src.inventory_dump.layout import INVENTORY_PAGES, REQUIRED_EQUIPMENT_SLOTS
from src.inventory_dump.models import (
    ExportFormat,
    ItemRecord,
    ScanDocument,
    ScanProgress,
    ScanResult,
    ScopeRecord,
    utc_now,
)
from src.inventory_dump.navigation import NavigationError, Navigator, ScanTarget
from src.inventory_dump.reader import ItemReader, ScanCancelledError
from src.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from threading import Event

    from src.type_aliases import JsonObject

LOGGER = logging.getLogger(__name__)


def scan_inventory(
    *, output_format: ExportFormat, cancel: Event, on_progress: Callable[[ScanProgress], None]
) -> ScanResult:
    """Run in the application's exclusive game-interaction worker, never in the GUI thread."""
    config = get_settings()
    output_format = ExportFormat(output_format)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = config.user_dir / "exports" / "inventory" / f"inventory-{stamp}.{output_format.value}"
    document = ScanDocument(locale=str(config.general.language), app_version=__version__)
    return Scanner(Navigator(cancel), ItemReader(cancel), SnapshotWriter(path, output_format), on_progress).run(
        document
    )


class Scanner:
    def __init__(
        self, navigator: Navigator, reader: ItemReader, writer: SnapshotWriter, progress: Callable[[ScanProgress], None]
    ) -> None:
        self.navigator = navigator
        self.reader = reader
        self.writer = writer
        self.progress = progress

    def run(self, document: ScanDocument) -> ScanResult:
        document.scopes.extend([
            ScopeRecord("stash", "all"),
            *(ScopeRecord("inventory", page) for page in INVENTORY_PAGES),
            ScopeRecord("equipped", "equipment"),
            ScopeRecord("equipped", "talisman"),
        ])
        self.writer.save(document)
        self.reader.open()
        try:
            self._report(document, "preparing", message="Detecting stash, inventory categories and equipped slots.")
            self.navigator.prepare()
            self._stash(document)
            self._inventory(document)
            incomplete = document.issues or document.failed_count or document.unverified_count
            document.status = "partial" if incomplete else "complete"
        except ScanCancelledError, GameInputCancelledError:
            document.status = "cancelled"
            document.issues.append(
                "Scanning cancelled; completed observations and the current partial item are retained."
            )
        except Exception as error:
            document.status = "partial" if document.items else "failed"
            document.issues.append(f"{type(error).__name__}: {error}")
            LOGGER.exception("Inventory scan stopped")
        finally:
            self.reader.close()
            for scope in document.scopes:
                if scope.status == "scanning":
                    scope.status = "partial"
                elif scope.status == "pending":
                    scope.status = "not_scanned"
                    scope.errors.append("This scope was not reached before the scan ended.")
            for item in document.items:
                if item.status == "pending":
                    item.status = "interrupted"
                    item.error = "Scan interrupted while reading this location."
            try:
                self.navigator.restore()
            except Exception as error:
                LOGGER.exception("Inventory scan could not restore the initial tabs")
                document.issues.append(f"UI restoration: {error}")
                if document.status == "complete":
                    document.status = "partial"
            document.finished_at = utc_now()
            self.writer.save(document)
        result = ScanResult(
            self.writer.path,
            document.status,
            len(document.items),
            document.failed_count,
            tuple(document.issues),
            document.unparsed_count,
            document.unverified_count,
        )
        self._report(document, "finished", message=str(result.output_path))
        return result

    def _stash(self, document: ScanDocument) -> None:
        discovery = self._scope(document, "stash", "all")
        try:
            tabs = self.navigator.stash_tabs()
        except NavigationError as error:
            discovery.status = "unavailable"
            discovery.errors.append(str(error))
            document.issues.append(str(error))
            self.writer.save(document)
            return
        discovery.status = "discovered"
        discovery.slots = len(tabs)
        document.scopes.extend(ScopeRecord("stash", tab.name) for tab in tabs)
        self.writer.save(document)
        for tab in tabs:
            scope = self._scope(document, "stash", tab.name)
            if not tab.icon_recognized:
                self._scope_error(
                    document, scope, NavigationError("Unrecognized or locked stash-tab icon; not clicked.")
                )
                continue
            try:
                self.navigator.select_tab(tab, stash=True)
                self._scan_scope(document, scope, self.navigator.grid_targets(tab.name, stash=True))
            except NavigationError as error:
                self._scope_error(document, scope, error)
                # An unexpected navigation state must not be followed by more clicks.
                raise

    def _inventory(self, document: ScanDocument) -> None:
        tabs = self.navigator.inventory_tabs()
        missing = set(INVENTORY_PAGES) - {tab.name for tab in tabs}
        for page in sorted(missing):
            message = f"Inventory category {page} could not be located."
            document.issues.append(message)
            scope = self._scope(document, "inventory", page)
            scope.status = "unavailable"
            scope.errors.append(message)
        for tab in tabs:
            scope = self._scope(document, "inventory", tab.name)
            try:
                self.navigator.select_tab(tab)
                self._scan_scope(document, scope, self.navigator.grid_targets(tab.name))
                if tab.name in {"equipment", "talisman"}:
                    equipped = self._scope(document, "equipped", tab.name)
                    targets = self.navigator.equipped_targets(talisman=tab.name == "talisman")
                    if not targets:
                        self._scope_error(document, equipped, NavigationError("No equipped slot frames detected."))
                    else:
                        self._scan_scope(document, equipped, targets)
                        if tab.name == "equipment":
                            detected = {target.location.slot for target in targets}
                            missing = set(REQUIRED_EQUIPMENT_SLOTS - detected)
                            if not any(slot.startswith("weapon_") for slot in detected):
                                missing.add("weapon slots")
                            if missing:
                                message = f"Equipment slot frames were not detected: {', '.join(sorted(missing))}."
                                equipped.status = "partial"
                                equipped.errors.append(message)
                                document.issues.append(message)
                                self.writer.save(document)
            except NavigationError as error:
                self._scope_error(document, scope, error)
                raise

    def _scan_scope(self, document: ScanDocument, scope: ScopeRecord, targets: list[ScanTarget]) -> None:
        scope.status, scope.slots = "scanning", len(targets)
        settled = {target.occupancy.get("icons_settled") for target in targets if target.occupancy is not None}
        scope.occupancy_settled = None if not settled else all(settled)
        self.writer.save(document)
        for target in targets:
            self.navigator.check()
            record = self._record(target)
            document.items.append(record)
            self._report(document, "scanning", target.location.label)
            try:
                self.reader.read(
                    record,
                    lambda point=target.location.center: self.navigator.hover(point),
                    self.navigator.neutral,
                    expected_occupied=target.occupied,
                )
            finally:
                # One durable write per item or unknown slot, before the next hover. Confirmed-empty
                # evidence rides along with the next write; cancel/failure paths still save in run().
                if self._settle_record(document, scope, record) != "empty":
                    self.writer.save(document)
        incomplete = any(
            not item.capture_complete or item.truncated
            for item in document.items
            if item.location.scope == scope.kind and item.location.page == scope.page
        )
        scope.status = "partial" if incomplete else "unverified" if scope.unverified_slots else "complete"
        if scope.unverified_slots:
            slots = ", ".join(str(entry["slot"]) for entry in scope.unverified_slots)
            document.issues.append(
                f"{scope.kind}/{scope.page}: 无法确认是否为空 / occupancy not confirmed for "
                f"{len(scope.unverified_slots)} slot(s): {slots}."
            )
        self.writer.save(document)

    @staticmethod
    def _record(target: ScanTarget) -> ItemRecord:
        record = ItemRecord(target.location, occupancy_evidence=target.occupancy)
        visual = (
            (target.favorite, "slot_screenshot_brightness", record.favorite_evidence),
            (target.junk, "slot_screenshot_template", record.junk_evidence),
        )
        for value, source, evidence in visual:
            if value is not None:
                evidence.append({"source": source, "verification": "unverified", "value": value})
        return record

    @staticmethod
    def _settle_record(document: ScanDocument, scope: ScopeRecord, record: ItemRecord) -> str:
        """Move slots without item evidence out of ``items``; return the slot outcome."""
        if record.status not in {"empty", "unverified"}:
            if record.status != "pending":
                scope.observed_items += 1
            return "item"
        if document.items and document.items[-1] is record:
            document.items.pop()
        evidence: JsonObject = {
            "slot": record.location.slot,
            "row": record.location.row,
            "column": record.location.column,
            "attempts": record.attempts,
            "visual_occupancy": record.occupancy_evidence,
            "raw_events": record.raw_events,
        }
        if record.status == "empty":
            scope.empty_slots += 1
            heard = any(event["text"] for event in record.raw_events)
            evidence["verification"] = "settled_visual_empty_and_no_item_tts"
            evidence["ambient_text_heard"] = heard
            scope.empty_slot_evidence.append(evidence)
            return "empty"
        evidence["reason"] = record.error
        scope.unverified_slots.append(evidence)
        return "unverified"

    def _scope_error(self, document: ScanDocument, scope: ScopeRecord, error: NavigationError) -> None:
        scope.status = "failed"
        scope.errors.append(str(error))
        document.issues.append(f"{scope.kind}/{scope.page}: {error}")
        self.writer.save(document)

    def _report(self, document: ScanDocument, stage: str, location: str = "", message: str = "") -> None:
        self.progress(ScanProgress(stage, location, len(document.items), document.failed_count, message))

    @staticmethod
    def _scope(document: ScanDocument, kind: str, page: str) -> ScopeRecord:
        return next(scope for scope in document.scopes if scope.kind == kind and scope.page == page)
