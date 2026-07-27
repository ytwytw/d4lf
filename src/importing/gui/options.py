"""Importer option dependencies and filename selection state."""

from typing import TYPE_CHECKING, Any

from src.importing import DEFAULT_FILENAME_PARTS, FilenamePart
from src.importing.gui.constants import FILENAME_PART_LABELS, GENERATE_DISABLED_FILENAME_PARTS_TOOLTIP
from src.localization import translate

if TYPE_CHECKING:
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton


class ImporterOptionsMixin:
    filename_input_box: QLineEdit
    filename_part_actions: dict[FilenamePart, QAction]
    filename_parts_summary_label: QLabel
    generate_button: QPushButton
    import_gas_checkbox: Any
    input_box: QLineEdit
    is_generating: bool
    require_all_gas_checkbox: Any
    settings: Any

    def _update_greater_affix_dependency(self) -> None:
        enabled = self.import_gas_checkbox.isChecked()
        self.require_all_gas_checkbox.setEnabled(enabled)
        if not enabled:
            self.require_all_gas_checkbox.setChecked(False)

    def _filename_part_setting(self, part: FilenamePart) -> bool:
        value = self.settings.value(self._filename_part_setting_key(part), "true")
        return value is True or str(value).casefold() == "true"

    def _handle_filename_part_toggled(self, part: FilenamePart, checked: bool) -> None:
        self.settings.setValue(self._filename_part_setting_key(part), checked)
        self._update_filename_parts_summary()
        self._update_generate_button_state()

    def _selected_filename_parts(self) -> tuple[FilenamePart, ...]:
        return tuple(part for part in DEFAULT_FILENAME_PARTS if self.filename_part_actions[part].isChecked())

    def _update_filename_parts_summary(self) -> None:
        labels = [
            translate(f"importer.filename_part.{part.value}", FILENAME_PART_LABELS[part])
            for part in self._selected_filename_parts()
        ]
        summary = "_".join(labels) + ".yaml" if labels else translate("common.none")
        self.filename_parts_summary_label.setText(translate("importer.default_filename", summary=summary))

    def _update_generate_button_state(self) -> None:
        if self.is_generating:
            self.generate_button.setEnabled(False)
            return
        url_ready = bool(self.input_box.text().strip())
        filename_ready = bool(self.filename_input_box.text().strip()) or bool(self._selected_filename_parts())
        self.generate_button.setEnabled(url_ready and filename_ready)
        if url_ready and not filename_ready:
            self.generate_button.setToolTip(
                translate("importer.filename_parts.required", GENERATE_DISABLED_FILENAME_PARTS_TOOLTIP)
            )
        elif not url_ready:
            self.generate_button.setToolTip(translate("importer.url.required"))
        else:
            self.generate_button.setToolTip("")

    @staticmethod
    def _filename_part_setting_key(part: FilenamePart) -> str:
        return f"filename_part_{part.value}"
