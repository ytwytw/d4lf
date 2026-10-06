from PyQt6.QtWidgets import QDialog

from src.equipment_knowledge import load_catalog
from src.native_filter import Action, Condition, ConditionKind, Rule
from src.native_filter.rule_editor import RuleDialog


def test_cancelled_rule_editor_does_not_mutate_original(native_app):
    parent = QDialog()
    original = Rule("原始", conditions=[Condition(ConditionKind.RARITY, mask=32)])
    dialog = RuleDialog(parent, load_catalog(), original)
    dialog.name.setText("改动")
    dialog.rule.conditions.clear()
    dialog.reject()
    assert original.name == "原始"
    assert len(original.conditions) == 1
    dialog = RuleDialog(parent, load_catalog(), original)
    dialog.action.setCurrentIndex(Action.HIDE_LABEL)
    dialog.enabled.setChecked(False)
    dialog._accept()
    assert dialog.rule.action == Action.HIDE_LABEL
    assert not dialog.rule.enabled
    parent.close()
