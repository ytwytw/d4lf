"""Single-choice inventory export UI; all game work runs in the owned worker."""

from typing import TYPE_CHECKING, override

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from src.inventory_dump import ExportFormat, ScanProgress, ScanResult

if TYPE_CHECKING:
    from pathlib import Path

    from PyQt6.QtGui import QCloseEvent

    from src.app.backend import BackendWorker


class InventoryDumpDialog(QDialog):
    def __init__(self, backend: BackendWorker | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._running = False
        self._closing = False
        self._output_path: Path | None = None
        self.setWindowTitle("完整物品导出")
        self.resize(720, 420)
        layout = QVBoxLayout(self)
        help_label = QLabel(
            "进入角色并打开仓库后开始。自动读取所有可访问仓库页、背包分类和穿戴物品，包含收藏和垃圾标记的物品。\n"
            "扫描时请保持游戏在前台，暂时不要移动鼠标。只读取物品，不改动物品。\n"
            "导出包含原始物品说明、可识别属性、位置和读取失败记录。应用内不进行 AI 分析。"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        choices = QHBoxLayout()
        choices.addWidget(QLabel("导出格式"))
        self.format_combo = QComboBox()
        for label, value in (("Markdown (.md)", "md"), ("纯文本 (.txt)", "txt"), ("JSON (.json)", "json")):
            self.format_combo.addItem(label, value)
        choices.addWidget(self.format_combo)
        choices.addStretch()
        layout.addLayout(choices)
        self.status_label = QLabel("等待开始")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("开始导出")
        self.cancel_button = QPushButton("取消并保存已读取物品")
        self.open_button = QPushButton("打开导出文件")
        self.cancel_button.setEnabled(False)
        self.open_button.setEnabled(False)
        for button in (self.start_button, self.cancel_button, self.open_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.start_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)
        self.open_button.clicked.connect(self._open_output)
        if backend is None:
            self.start_button.setEnabled(False)
            self.status_label.setText("物品扫描需要 Windows 游戏运行环境。")
        else:
            backend.dump_progress.connect(self._on_progress)
            backend.dump_finished.connect(self._on_finished)
            backend.dump_failed.connect(self._on_failed)

    def _start(self) -> None:
        if self._backend is None:
            return
        self._set_running(running=True)
        # A new scan must never offer the previous scan's file as its result.
        self._output_path = None
        self.open_button.setEnabled(False)
        self.details.clear()
        self.status_label.setText("正在准备扫描，接下来将切回游戏…")
        self._backend.start_inventory_dump(ExportFormat(self.format_combo.currentData()))

    def _cancel(self) -> None:
        if self._backend is not None:
            self.cancel_button.setEnabled(False)
            self.status_label.setText("正在停止并保存已读取的物品…")
            self._backend.cancel_inventory_dump()

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.start_button.setEnabled(not running)
        self.format_combo.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def _on_progress(self, progress: ScanProgress) -> None:
        self.status_label.setText(
            f"已读取 {progress.scanned} 件 · 未完整读取 {progress.failed} 件 · {progress.location}"
        )
        if progress.message:
            self.details.append(progress.message)

    def _on_finished(self, result: ScanResult) -> None:
        self._set_running(running=False)
        self._output_path = result.output_path
        self.open_button.setEnabled(result.output_path.exists())
        labels = {
            "complete": "完成",
            "partial": "部分完成",
            "cancelled": "已取消，已保存部分结果",
            "failed": "扫描失败",
        }
        self.status_label.setText(
            f"{labels.get(result.status, result.status)} · {result.item_count} 件物品 · 未完整读取 {result.failed_count} 件"
        )
        self.details.append(str(result.output_path))
        if result.unverified_count:
            self.details.append(
                f"{result.unverified_count} 个槽位既没有读到物品说明，也没有明确的空槽位提示，"
                "无法确认是否为空；导出文件已列出这些位置，因此本次结果不是完整清单。"
            )
        if result.unparsed_count:
            self.details.append(
                f"{result.unparsed_count} 件物品的原文已完整导出，但现有词库未能解析；原始说明与直接读取的字段均已保留。"
            )
        for issue in result.issues:
            self.details.append(issue)
        if self._closing:
            self.close()

    def _on_failed(self, message: str) -> None:
        self._set_running(running=False)
        self._output_path = None
        self.open_button.setEnabled(False)
        self.status_label.setText("未完成导出")
        self.details.append(message)
        if self._closing:
            self.close()

    def _open_output(self) -> None:
        if self._output_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._output_path)))

    @override
    def reject(self) -> None:
        if self._running:
            self._closing = True
            self._cancel()
            return
        super().reject()

    @override
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if self._running:
            self._closing = True
            self._cancel()
            if a0 is not None:
                a0.ignore()
            return
        super().closeEvent(a0)
