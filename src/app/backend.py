"""Windows backend composition used by the desktop shell."""

import logging
import sys
from threading import Event

from PyQt6.QtCore import QObject, pyqtSignal

from src.autoupdater import notify_if_update
from src.desktop import shutdown_ui_thread
from src.diagnostics import begin_shutdown
from src.settings import get_settings

if sys.platform == "win32":
    from src import perception as _perception
    from src.app.handler import ScriptHandler
    from src.automation import WindowSpec, start_detecting_window, stop_detecting_window
    from src.item.filter import Filter
    from src.overlay import Overlay
    from src.perception import game_window_ready
else:
    _perception = None

from typing import TYPE_CHECKING

from src.app.startup import check_for_proper_tts_configuration

if TYPE_CHECKING:
    from types import ModuleType

    from src.inventory_dump import ExportFormat

LOGGER = logging.getLogger(__name__)


def get_perception_module() -> ModuleType | None:
    """Return the active perception adapter, or ``None`` in GUI-only mode."""
    return _perception


class BackendWorker(QObject):
    """Own the game-facing runtime and expose its lifecycle to the Qt shell."""

    finished = pyqtSignal()
    dump_progress = pyqtSignal(object)
    dump_finished = pyqtSignal(object)
    dump_failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.script_handler: ScriptHandler | None = None
        self._stop_requested = Event()

    def request_stop(self) -> None:
        """Cancel waits and stop accepting game input immediately, from any thread."""
        begin_shutdown()
        self._stop_requested.set()
        if self.script_handler is not None:
            self.script_handler.cancel_inventory_dump()

    def start_inventory_dump(self, output_format: ExportFormat) -> None:
        if self.script_handler is None:
            self.dump_failed.emit("请先进入游戏角色，等待 D4LF 连接到游戏。")
            return
        try:
            self.script_handler.start_inventory_dump(
                output_format, self.dump_progress.emit, self.dump_finished.emit, self.dump_failed.emit
            )
        except RuntimeError as exc:
            self.dump_failed.emit(str(exc))

    def cancel_inventory_dump(self) -> None:
        if self.script_handler is not None:
            self.script_handler.cancel_inventory_dump()

    def run(self) -> None:
        if sys.platform != "win32":
            LOGGER.info("GUI-only mode is active on non-Windows. Backend runtime is disabled.")
            self.finished.emit()
            return

        try:
            self._run_windows()
        except Exception:
            LOGGER.exception("Game backend failed")
        finally:
            self.request_stop()
            for cleanup in (self._stop_scripts, stop_detecting_window, shutdown_ui_thread):
                try:
                    cleanup()
                except Exception:
                    LOGGER.exception("Game backend cleanup failed")
            self.finished.emit()

    def _stop_scripts(self) -> None:
        if self.script_handler is not None:
            self.script_handler.shutdown()

    def _run_windows(self) -> None:
        if self._stop_requested.is_set():
            return
        _perception.start_connection()
        Filter().load_files()
        if getattr(sys, "frozen", False):
            notify_if_update()
        else:
            LOGGER.debug("Skipping autoupdate check as code is being run from source.")
        if self._stop_requested.is_set():
            return
        start_detecting_window(WindowSpec(get_settings().advanced_options.process_name))
        while not game_window_ready():
            if self._stop_requested.wait(0.2):
                return
        if self._stop_requested.wait(0.5):
            return
        self.script_handler = ScriptHandler()
        if self._stop_requested.is_set():
            return
        check_for_proper_tts_configuration()
        if not self._stop_requested.is_set():
            Overlay().run(self._stop_requested)


def run_backend() -> None:
    """Run the game backend synchronously for the console-only entry point."""
    worker = BackendWorker()
    worker.run()
