import base64
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QMessageBox

from src.native_filter import NativeFilterDialog, decode_filter
from src.profiles import DynamicItemFilterModel, ItemFilterModel, ProfileModel


def test_editor_opens_independent_and_discovers_both_yaml_extensions(native_app, tmp_path):
    directory = tmp_path / "profiles"
    directory.mkdir()
    (directory / "first.yml").write_text("Affixes: []", encoding="utf-8")
    (directory / "second.yaml").write_text("Affixes: []", encoding="utf-8")
    dialog = NativeFilterDialog(profile_name="first")
    assert dialog.profiles.currentText() == "first"
    assert dialog.profiles.count() == 3
    assert "当前不会隐藏" in dialog.status.text()
    assert decode_filter(dialog.code.toPlainText()).rules[0].name == "显示所有物品"
    assert not dialog.drop_policy.isChecked()
    dialog.close()


def test_unknown_import_locks_controls_but_keeps_code(native_app):
    dialog = NativeFilterDialog()
    payload = base64.b64decode(dialog.code.toPlainText()) + b"\x48\x01"
    code = base64.b64encode(payload).decode()
    dialog.saved.document = decode_filter(code)
    dialog._refresh()
    assert all(not button.isEnabled() for button in dialog.edit_buttons)
    assert dialog.name.isReadOnly()
    assert dialog.code.toPlainText() == code
    dialog.close()


def test_generate_new_copy_preserves_original_save_path(native_app, monkeypatch, tmp_path):
    profile = ProfileModel.model_construct(
        name="test",
        affixes=[DynamicItemFilterModel.model_construct(root={"保留": ItemFilterModel.model_construct(min_power=750)})],
    )
    monkeypatch.setattr(
        "src.native_filter.dialog.ProfileDocumentStore.default",
        lambda: SimpleNamespace(load=lambda _path: SimpleNamespace(profile=profile)),
    )
    dialog = NativeFilterDialog()
    dialog.profiles.addItem("test", str(tmp_path / "test.yaml"))
    dialog.profiles.setCurrentIndex(1)
    previous_path = tmp_path / "manual.json"
    dialog.path = previous_path
    dialog.drop_policy.setChecked(True)
    dialog._generate()
    assert dialog.path is None
    assert dialog.saved.generation_policy is not None
    assert dialog.saved.generation_policy.preserve_sanctified is False
    assert dialog.saved.document.hides_items
    assert not previous_path.exists()
    dialog.dirty = False
    dialog.close()


def test_declining_replace_keeps_manual_edits(native_app, monkeypatch):
    dialog = NativeFilterDialog()
    dialog.saved.document.name = "我的修改"
    dialog.dirty = True
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    dialog._new()
    assert dialog.saved.document.name == "我的修改"
    dialog.dirty = False
    dialog.close()


@pytest.mark.parametrize(
    "error", [FileNotFoundError("catalog-73552.json"), ValueError("Knowledge snapshot checksum mismatch: items.json")]
)
def test_unavailable_catalog_shows_error_and_can_close(native_app, monkeypatch, error):
    def unavailable():
        raise error

    monkeypatch.setattr("src.native_filter.dialog.load_catalog", unavailable)
    dialog = NativeFilterDialog(profile_name="Build A")
    assert "原生过滤器不可用" in dialog.status.text()
    assert str(error) in dialog.status.text()
    assert "重新解压完整应用" in dialog.status.text()
    assert not hasattr(dialog, "profiles")
    assert not hasattr(dialog, "code")
    assert dialog.close()
