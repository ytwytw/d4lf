import os
from threading import Thread
from typing import Never

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from src.importing import ImportRequest, ImportResult, VariantMetadata
from src.importing.contracts import ImportSession
from src.importing.d2core.errors import NO_USABLE_VARIANT, D2CoreImportError
from src.importing.d4builds.metadata import D4BuildsError
from src.importing.gui import support
from src.importing.gui import window as window_module
from src.importing.gui.support import FetchVariantsWorker, ImportWorker, WorkerSignals, run_import
from src.importing.maxroll.planner import MaxrollError
from src.profiles import ProfileModel


def test_import_support_exposes_worker_and_headless_runner() -> None:
    assert callable(run_import)
    assert ImportWorker is not None
    assert WorkerSignals is not None


def test_run_import_reuses_explicit_session(monkeypatch) -> None:
    class FakeSource:
        name = "fixture"

        def fetch_variants(self, request):
            return []

        def import_build(self, request):
            return ImportResult(source_name=self.name, selected_variant="one", profile=ProfileModel(name="profile"))

    session = ImportSession(FakeSource())
    captured: list[ImportSession] = []
    original = support.import_build

    def spy_import_build(request: ImportRequest, *, session: ImportSession | None = None) -> ImportResult:
        assert session is not None
        captured.append(session)
        return original(request, session=session)

    monkeypatch.setattr(support, "import_build", spy_import_build)
    run_import(request=ImportRequest("https://fixture.invalid/build"), session=session)

    assert captured == [session]
    assert not session.closed
    session.close()


def test_fetch_worker_uses_explicit_session_without_opening_another() -> None:
    class FakeSession:
        name = "fixture"

        def fetch_variants(self, request):
            return []

        def import_build(self, request) -> Never:
            raise AssertionError

        def close(self) -> None:
            pass

    session = ImportSession(FakeSession())
    assert not hasattr(support, "open_session")
    worker = FetchVariantsWorker(
        request=ImportRequest("https://fixture.invalid/build"), finished=lambda: None, session=session
    )
    worker.run()

    assert worker.session is session


def test_workers_do_not_replay_expected_d2core_terminal_errors(caplog) -> None:
    class FailedSession:
        name = "d2core"

        def fetch_variants(self, request) -> Never:
            raise D2CoreImportError(NO_USABLE_VARIANT, "No selected d2core Variant could be resolved")

        def import_build(self, request) -> Never:
            raise D2CoreImportError(NO_USABLE_VARIANT, "No selected d2core Variant could be resolved")

        def close(self) -> None:
            pass

    caplog.set_level("ERROR")
    session = ImportSession(FailedSession())
    ImportWorker(ImportRequest("https://d2core.com/d4/planner?bd=offline"), lambda: None, session).run()
    FetchVariantsWorker(ImportRequest("https://d2core.com/d4/planner?bd=offline"), lambda: None, session).run()

    assert not caplog.records


def test_workers_signal_expected_provider_errors_without_replaying_logs(caplog) -> None:
    class FailedSession:
        name = "d4builds"

        def fetch_variants(self, request) -> Never:
            message = "No variants could be extracted"
            raise D4BuildsError(message)

        def import_build(self, request) -> Never:
            message = "No variants could be extracted"
            raise D4BuildsError(message)

        def close(self) -> None:
            pass

    caplog.set_level("ERROR")
    session = ImportSession(FailedSession())
    messages = []
    finished = []
    for worker_type in (ImportWorker, FetchVariantsWorker):
        worker = worker_type(
            ImportRequest("https://d4builds.gg/builds/example"), lambda: finished.append(True), session
        )
        worker.signals.failed.connect(messages.append)
        worker.run()

    assert not caplog.records
    assert messages == ["No variants could be extracted"] * 2
    assert finished == [True, True]


@pytest.fixture
def importer_window(tmp_path, monkeypatch, mock_ini_loader):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "importer.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(window_module, "QSettings", lambda *_args: settings)
    window = window_module.ImporterWindow()
    yield app, window
    window.close()
    app.processEvents()


@pytest.mark.parametrize("stage", ["import", "discovery", "persist"])
def test_worker_source_error_is_visible_in_importer_without_success(importer_window, monkeypatch, stage) -> None:
    app, window = importer_window
    message = "Maxroll visible profile 5 no longer exists. Choose a current visible variant or a valid planner link."

    class Source:
        name = "maxroll"
        close_calls = 0

        def fetch_variants(self, request):
            if stage == "discovery":
                raise MaxrollError(message)
            return [VariantMetadata("1", "Visible")]

        def import_build(self, request) -> Never:
            raise MaxrollError(message)

        def close(self):
            self.close_calls += 1

    class ImmediatePool:
        def start(self, worker):
            worker.run()

    source = Source()
    monkeypatch.setattr(window_module, "open_session", lambda _url: ImportSession(source))
    monkeypatch.setattr(window_module, "THREADPOOL", ImmediatePool())
    monkeypatch.setattr(window_module, "select_variants_dialog", lambda *_args: ["1"])
    completed = []
    window.import_completed.connect(lambda: completed.append(True))
    window.multi_build_checkbox.setChecked(stage != "import")
    window.input_box.setText("https://maxroll.gg/d4/build-guides/minion-necromancer-guide")
    window._generate_button_click()
    app.processEvents()

    assert f"Import failed: {message}" in window.log_output.toPlainText()
    assert not completed
    assert not window.is_generating
    assert window.generate_button.isEnabled()
    assert source.close_calls == 1


def test_queued_worker_failure_then_success_does_not_keep_failure_state(importer_window, monkeypatch) -> None:
    app, window = importer_window

    class Source:
        name = "maxroll"
        should_fail = True

        def fetch_variants(self, request):
            return []

        def import_build(self, request):
            if self.should_fail:
                message = "Choose a current visible variant."
                raise MaxrollError(message)
            return ImportResult(source_name=self.name, selected_variant="Visible", profile=ProfileModel(name="test"))

        def close(self):
            pass

    class QueuedPool:
        def start(self, worker):
            thread = Thread(target=worker.run)
            thread.start()
            thread.join(timeout=5)
            assert not thread.is_alive()

    source = Source()
    monkeypatch.setattr(window_module, "open_session", lambda _url: ImportSession(source))
    monkeypatch.setattr(window_module, "THREADPOOL", QueuedPool())
    window.input_box.setText("https://maxroll.gg/d4/planner/test#1")
    completed = []
    window.import_completed.connect(lambda: completed.append(True))
    window._generate_button_click()
    app.processEvents()

    assert "Import failed: Choose a current visible variant." in window.log_output.toPlainText()
    assert completed == []
    assert window.generate_button.isEnabled()

    source.should_fail = False
    window._generate_button_click()
    app.processEvents()
    assert completed == [True]
    assert "Import failed:" not in window.log_output.toPlainText()
