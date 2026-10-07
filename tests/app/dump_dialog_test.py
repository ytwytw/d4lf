from threading import Thread

import pytest
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication

from src.app.backend import BackendWorker
from src.app.dump_dialog import InventoryDumpDialog
from src.inventory_dump import ExportFormat, ScanProgress, ScanResult


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_format_is_only_scan_option_and_start_disables_changes(app, mocker):
    backend = BackendWorker()
    start = mocker.patch.object(backend, "start_inventory_dump")
    dialog = InventoryDumpDialog(backend)
    dialog.format_combo.setCurrentIndex(dialog.format_combo.findData("json"))
    dialog.start_button.click()
    start.assert_called_once_with(ExportFormat.JSON)
    assert not dialog.start_button.isEnabled()
    assert not dialog.format_combo.isEnabled()
    assert dialog.cancel_button.isEnabled()
    dialog._on_failed("offline fixture")
    dialog.close()


def test_closing_a_running_dump_cancels_and_waits_for_saved_result(app, mocker, tmp_path):
    backend = BackendWorker()
    mocker.patch.object(backend, "start_inventory_dump")
    cancel = mocker.patch.object(backend, "cancel_inventory_dump")
    dialog = InventoryDumpDialog(backend)
    dialog.start_button.click()
    event = QCloseEvent()
    dialog.closeEvent(event)
    assert not event.isAccepted()
    cancel.assert_called_once()
    output = tmp_path / "partial.json"
    output.write_text("{}", encoding="utf-8")
    backend.dump_finished.emit(ScanResult(output, "cancelled", 3, 1, ("scope not visited",)))
    assert not dialog._running
    assert "3" in dialog.status_label.text()
    assert "scope not visited" in dialog.details.toPlainText()
    assert dialog.open_button.isEnabled()


def test_progress_from_worker_is_delivered_via_gui_event_loop(app):
    backend = BackendWorker()
    dialog = InventoryDumpDialog(backend)
    thread = Thread(target=lambda: backend.dump_progress.emit(ScanProgress("scanning", "stash/1/2", 7, 1)))
    thread.start()
    thread.join(timeout=1)
    assert dialog.status_label.text() == "等待开始"
    app.processEvents()
    assert "7" in dialog.status_label.text()
    assert "stash/1/2" in dialog.status_label.text()
    dialog.close()


def test_escape_cannot_abandon_the_running_worker(app, mocker):
    backend = BackendWorker()
    mocker.patch.object(backend, "start_inventory_dump")
    cancel = mocker.patch.object(backend, "cancel_inventory_dump")
    dialog = InventoryDumpDialog(backend)
    dialog.start_button.click()
    dialog.reject()
    assert dialog._running
    assert dialog._closing
    cancel.assert_called_once()
    dialog._on_failed("cancelled fixture")


def test_new_scan_and_failure_never_offer_the_previous_export(app, mocker, tmp_path):
    backend = BackendWorker()
    mocker.patch.object(backend, "start_inventory_dump")
    dialog = InventoryDumpDialog(backend)
    previous = tmp_path / "inventory-previous.md"
    previous.write_text("old", encoding="utf-8")
    dialog.start_button.click()
    backend.dump_finished.emit(ScanResult(previous, "complete", 1, 0))
    assert dialog.open_button.isEnabled()
    dialog.start_button.click()
    assert not dialog.open_button.isEnabled()
    assert dialog._output_path is None
    backend.dump_failed.emit("PermissionError: denied")
    assert not dialog.open_button.isEnabled()
    assert dialog._output_path is None
    dialog.close()


def test_unverified_slots_are_reported_as_an_incomplete_inventory(app, mocker, tmp_path):
    backend = BackendWorker()
    mocker.patch.object(backend, "start_inventory_dump")
    dialog = InventoryDumpDialog(backend)
    output = tmp_path / "partial.json"
    output.write_text("{}", encoding="utf-8")
    dialog.start_button.click()
    backend.dump_finished.emit(ScanResult(output, "partial", 16, 0, ("equipped/talisman: seal",), 0, 1))
    assert "1 个槽位" in dialog.details.toPlainText()
    assert "不是完整清单" in dialog.details.toPlainText()
    dialog.close()
