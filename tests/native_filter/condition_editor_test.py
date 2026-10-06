import pytest
from PyQt6.QtWidgets import QDialog

from src.equipment_knowledge import load_catalog
from src.native_filter import Condition, ConditionKind, NativeFilterError
from src.native_filter.condition_editor import ConditionDialog, parse_ids


def test_form_uses_names_and_preserves_ga_selection(native_app):
    source = Condition(ConditionKind.REQUIRED_AFFIXES, sno_ids=(577173, 583654), ga_sno_ids=(583654,), min_count=2)
    parent = QDialog()
    dialog = ConditionDialog(parent, load_catalog(), source)
    assert not dialog.advanced.isChecked()
    assert "未知 ID" not in dialog.selection.text()
    assert "583654" not in dialog.selection.text()
    dialog._accept()
    assert dialog.result_condition == source
    parent.close()


def test_rarity_selector_roundtrips(native_app):
    parent = QDialog()
    dialog = ConditionDialog(parent, load_catalog(), Condition(ConditionKind.RARITY, mask=40))
    assert dialog.mask_checks[8].isChecked()
    assert dialog.mask_checks[32].isChecked()
    dialog._accept()
    assert dialog.result_condition is not None
    assert dialog.result_condition.mask == 40
    parent.close()


def test_manual_id_entry_validates_and_deduplicates():
    assert parse_ids("123，456, 123") == (123, 456)
    with pytest.raises(NativeFilterError):
        parse_ids("unknown")
    with pytest.raises(NativeFilterError):
        parse_ids("-1")
