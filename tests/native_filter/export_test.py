from PyQt6.QtWidgets import QApplication, QDialog

from src.native_filter import NativeFilter, decode_filter
from src.native_filter.export import copy_code, export_code


def test_explicit_clipboard_and_text_exports(native_app, monkeypatch, tmp_path):
    parent = QDialog()
    document = NativeFilter("可复制")
    copy_code(parent, document)
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert decode_filter(clipboard.text()).name == document.name
    target = tmp_path / "filter.txt"

    def choose_export_path(_parent, _title, suggested_path, _filter):
        assert suggested_path == str(tmp_path / "native_filters" / "filter.txt")
        assert (tmp_path / "native_filters").is_dir()
        return str(target), ""

    monkeypatch.setattr("src.native_filter.export.QFileDialog.getSaveFileName", choose_export_path)
    export_code(parent, document)
    assert decode_filter(target.read_text(encoding="utf-8")).name == document.name
    parent.close()
