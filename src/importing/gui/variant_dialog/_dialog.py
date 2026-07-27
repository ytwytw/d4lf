from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from src.desktop.widgets import CheckmarkCheckBox
from src.localization import translate

if TYPE_CHECKING:
    from src.importing.contracts import VariantMetadata


def select_variants_dialog(parent, variants: list[VariantMetadata], source_name: str) -> list[str] | None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(translate("importer.variants.title"))
    dialog.setMinimumWidth(300)
    layout = QVBoxLayout(dialog)
    label = QLabel(translate("importer.variants.body", count=len(variants), source=source_name))
    layout.addWidget(label)
    checkboxes = []
    for i, variant in enumerate(variants):
        cb = CheckmarkCheckBox(variant.name or translate("importer.variants.fallback", number=i + 1))
        cb.setChecked(True)
        checkboxes.append((variant.id, cb))
        layout.addWidget(cb)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return [variant_id for variant_id, cb in checkboxes if cb.isChecked()]
    return None
