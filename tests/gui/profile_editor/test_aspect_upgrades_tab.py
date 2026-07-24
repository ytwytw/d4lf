import os
from typing import override

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

from src.gui.models import catalog_display
from src.gui.models import dialog as dialog_module
from src.gui.models.dialog import AddAspectUpgrade
from src.gui.profile_editor.aspect_upgrades_tab import AspectUpgradesTab


class _AcceptedDialog(QDialog):
    def __init__(self, value: str):
        super().__init__()
        self._value = value

    @override
    def exec(self) -> int:
        return QDialog.DialogCode.Accepted

    def get_value(self) -> str:
        return self._value


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _button(tab: AspectUpgradesTab, text: str) -> QPushButton:
    return next(btn for btn in tab.findChildren(QPushButton) if btn.text() == text)


def test_add_aspect_adds_rule_to_list_and_widget(qapp, monkeypatch):
    monkeypatch.setattr(
        "src.gui.profile_editor.aspect_upgrades_tab.AddAspectUpgrade", lambda *_args, **_kwargs: _AcceptedDialog("new")
    )

    aspects = ["old"]
    tab = AspectUpgradesTab(aspects)
    tab.load()

    _button(tab, "Add Aspect").click()

    assert aspects == ["old", "new"]
    assert tab.list_widget.count() == 2
    item = tab.list_widget.item(1)
    assert item is not None
    assert item.text() == "new"


def test_remove_selected_with_no_selection_shows_warning_and_does_not_crash(qapp, monkeypatch):
    warnings: list[tuple[str, str]] = []

    def _warning(parent, title: str, message: str):
        warnings.append((title, message))

    monkeypatch.setattr(QMessageBox, "warning", _warning)

    aspects = ["old"]
    tab = AspectUpgradesTab(aspects)
    tab.load()

    _button(tab, "Remove Selected").click()

    assert aspects == ["old"]
    assert warnings == [("Warning", "Select at least one rule to remove.")]


def test_aspect_upgrade_dialog_and_list_display_localized_names_but_keep_canonical_ids(qapp, monkeypatch):
    class Catalog:
        grammar = type("Grammar", (), {"locale": "zhCN"})()
        aspect_list = ["accelerating", "aggressive", "malicious", "virulent"]
        aspect_dict = {"accelerating": "加速", "aggressive": "侵略性", "malicious": "恶毒", "virulent": "恶毒"}

        def resolve_aspect(self, value):
            if value == "恶毒":
                return "malicious"
            reverse = {display: canonical for canonical, display in self.aspect_dict.items()}
            return reverse.get(value, value if value in self.aspect_dict else None)

    catalog = Catalog()
    monkeypatch.setattr(catalog_display, "Dataloader", lambda: catalog)
    monkeypatch.setattr(
        catalog_display,
        "IniConfigLoader",
        lambda: type("Config", (), {"general": type("General", (), {"language": "zhCN"})()})(),
    )
    monkeypatch.setattr(dialog_module, "Dataloader", lambda: catalog)

    dialog = AddAspectUpgrade([])
    accelerating_index = dialog.name_input.findData("accelerating")
    assert accelerating_index >= 0
    assert dialog.name_input.itemText(accelerating_index) == "加速"
    dialog.name_input.setCurrentIndex(accelerating_index)
    assert dialog.name_input.currentData() == "accelerating"
    assert dialog.get_value() == "accelerating"
    dialog.name_input.setEditText("侵略性")
    assert dialog.get_value() == "aggressive"
    virulent_index = dialog.name_input.findData("virulent")
    assert virulent_index >= 0
    dialog.name_input.setCurrentIndex(virulent_index)
    assert dialog.get_value() == "virulent"

    aspects = ["accelerating"]
    tab = AspectUpgradesTab(aspects)
    tab.load()
    item = tab.list_widget.item(0)
    assert item is not None
    assert item.text() == "加速"
    assert aspects == ["accelerating"]
