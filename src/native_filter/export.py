"""Explicit clipboard and text-file export actions for the editor."""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.native_filter.codec import encode_filter
from src.native_filter.models import NativeFilterError
from src.settings import get_settings

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from src.native_filter.models import NativeFilter


def default_directory() -> Path:
    directory = get_settings().user_dir / "native_filters"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def copy_code(parent: QWidget, document: NativeFilter) -> None:
    try:
        code = encode_filter(document)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(code)
    except NativeFilterError as error:
        QMessageBox.warning(parent, "导出失败", str(error))


def export_code(parent: QWidget, document: NativeFilter) -> None:
    try:
        code = encode_filter(document)
        path, _ = QFileDialog.getSaveFileName(
            parent, "导出游戏代码", str(default_directory() / "filter.txt"), "文本文件 (*.txt)"
        )
        if path:
            Path(path).write_text(code + "\n", encoding="utf-8")
    except (OSError, NativeFilterError) as error:
        QMessageBox.warning(parent, "导出失败", str(error))
