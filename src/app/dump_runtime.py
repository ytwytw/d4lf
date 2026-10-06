"""Cooperative inventory export ownership, independent of the Qt event loop."""

import logging
from threading import Event, Thread
from typing import TYPE_CHECKING

from src.app.interaction import GAME_INTERACTION_LOCK
from src.automation import move_window_to_foreground
from src.diagnostics.tts_capture import APP_TTS_CAPTURE
from src.inventory_dump import scan_inventory
from src.overlay import is_open

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.app.handler import ScriptHandler
    from src.inventory_dump import ExportFormat, ScanProgress, ScanResult

LOGGER = logging.getLogger(__name__)


class InventoryDumpRuntime:
    _dump_thread: Thread | None = None

    def _init_inventory_dump(self) -> None:
        self._dump_cancel = Event()
        self._dump_thread = None

    @property
    def inventory_dump_running(self) -> bool:
        return self._dump_thread is not None

    def cancel_inventory_dump(self) -> None:
        self._dump_cancel.set()

    def wait_for_inventory_dump(self, timeout: float | None = None) -> bool:
        """Join the export worker; return whether it finished (a timeout leaves it running)."""
        thread = self._dump_thread
        if thread is not None:
            thread.join(timeout)
            return not thread.is_alive()
        return True

    def start_inventory_dump(
        self: ScriptHandler,
        output_format: ExportFormat,
        on_progress: Callable[[ScanProgress], None],
        on_done: Callable[[ScanResult], None],
        on_error: Callable[[str], None],
    ) -> None:
        with GAME_INTERACTION_LOCK:
            if self._shutting_down:
                message = "D4LF 正在关闭。"
                raise RuntimeError(message)
            if self._config.advanced_options.vision_mode_only:
                message = "当前开启了“仅视觉模式”，它禁止自动点击。请在设置中关闭后再扫描物品。"
                raise RuntimeError(message)
            if self.inventory_dump_running or self.loot_interaction_thread is not None:
                message = "另一项游戏操作正在运行，请先结束它。"
                raise RuntimeError(message)
            if self.paragon_overlay_thread is not None or is_open() or APP_TTS_CAPTURE.is_active:
                message = "请先关闭巅峰／信息面板和诊断录制，再开始物品导出。"
                raise RuntimeError(message)
            self._dump_cancel.clear()
            self._dump_thread = Thread(
                target=self._run_inventory_dump,
                args=(output_format, on_progress, on_done, on_error),
                name="inventory-dump",
                daemon=False,
            )
            self._dump_thread.start()

    def _run_inventory_dump(
        self: ScriptHandler,
        output_format: ExportFormat,
        on_progress: Callable[[ScanProgress], None],
        on_done: Callable[[ScanResult], None],
        on_error: Callable[[str], None],
    ) -> None:
        resume_vision = self.vision_mode.running()
        result = None
        error = ""
        try:
            if resume_vision:
                self.vision_mode.stop()
            if not self._dump_cancel.is_set():
                move_window_to_foreground(self._win_spec)
            result = scan_inventory(output_format=output_format, cancel=self._dump_cancel, on_progress=on_progress)
        except Exception as exc:
            LOGGER.exception("Inventory export failed")
            error = str(exc)
        finally:
            with GAME_INTERACTION_LOCK:
                try:
                    if resume_vision and not self._shutting_down and not self.vision_mode.running():
                        self.vision_mode.start()
                except Exception:
                    LOGGER.exception("Could not restore vision after inventory export")
                self._dump_thread = None
        if result is not None:
            on_done(result)
        else:
            on_error(error or "物品导出未能完成。")
