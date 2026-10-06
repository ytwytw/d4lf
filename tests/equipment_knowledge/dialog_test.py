import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from src.equipment_knowledge import EquipmentKnowledgeDialog
from src.equipment_knowledge.profile import ProfileEquipment


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_independent_search_and_affix_browser(app):
    dialog = EquipmentKnowledgeDialog()
    assert dialog.results.count() == 380
    dialog.search.setText("命运之拳")
    assert dialog.results.count() == 1
    assert "250 - 300" in dialog.details.toPlainText()
    dialog.category.setCurrentIndex(1)
    dialog.search.setText("Runeword_RegenMana_Flat_15")
    assert dialog.results.count() == 1
    assert "法力回复" in dialog.details.toPlainText()
    dialog.close()


def test_selected_profile_limits_to_exact_id_and_can_return_to_all(app, monkeypatch):
    monkeypatch.setattr(
        "src.equipment_knowledge.dialog.load_profile_equipment",
        lambda name, _catalog: ProfileEquipment(name, frozenset({186283}), frozenset(), ()),
    )
    dialog = EquipmentKnowledgeDialog(profile_name="Build A")
    assert dialog.results.count() == 1
    assert "命运之拳" in dialog.details.toPlainText()
    dialog.profile_only.setChecked(False)
    assert dialog.results.count() == 380
    dialog.close()


def test_missing_profile_does_not_prevent_independent_use(app, monkeypatch):
    def missing(name, catalog):
        raise FileNotFoundError(name)

    monkeypatch.setattr("src.equipment_knowledge.dialog.load_profile_equipment", missing)
    dialog = EquipmentKnowledgeDialog(profile_name="missing")
    assert dialog.results.count() == 380
    assert "关联 Profile 失败" in dialog.profile_status.text()
    dialog.close()
