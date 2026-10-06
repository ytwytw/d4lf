from PyQt6.QtWidgets import QDialog

from src.equipment_knowledge import load_catalog
from src.native_filter.picker import IdPicker


def test_search_does_not_drop_selected_type(native_app):
    parent = QDialog()
    dialog = IdPicker(parent, load_catalog(), "type", (446832,))
    dialog._search("unmatched string")
    assert dialog.selected_ids() == (446832,)
    assert dialog.entries.count() > 0
    parent.close()


def test_picker_preserves_imported_variant_subset_and_unknown_ids(native_app):
    parent = QDialog()
    selected = (583654, 4294967294)
    dialog = IdPicker(parent, load_catalog(), "affix", selected)
    assert set(dialog.selected_ids()) == set(selected)
    parent.close()
