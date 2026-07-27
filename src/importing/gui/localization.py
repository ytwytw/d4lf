"""Live localization behavior for the build importer window."""

from typing import TYPE_CHECKING, Any

from src.importing import DEFAULT_FILENAME_PARTS
from src.importing.gui.constants import _CHECKBOX_CONFIGS, FILENAME_PART_LABELS, INSTRUCTIONS_TEXT
from src.localization import translate
from src.settings import LANGUAGE_SETTING_KEYS, get_settings, has_any_changed


class ImporterWindowLocalization:
    _config: Any
    _update_filename_parts_summary: Any
    _update_generate_button_state: Any
    filename_input_box: Any
    filename_label: Any
    filename_part_actions: Any
    filename_parts_button: Any
    generate_button: Any
    instructions_label: Any
    instructions_text: Any
    is_generating: bool
    language_changed_signal: Any
    log_label: Any
    url_label: Any

    if TYPE_CHECKING:

        def setWindowTitle(self, a0: str | None) -> None: ...  # ruff:ignore[invalid-function-name]

    def _setup_localization(self) -> None:
        self._config = get_settings()
        self.language_changed_signal.connect(self.retranslate_ui)
        self._config.register_change_listener(self._queue_language_change)
        self.retranslate_ui()

    def _queue_language_change(self, changed_keys) -> None:
        if has_any_changed(changed_keys, LANGUAGE_SETTING_KEYS):
            self.language_changed_signal.emit()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(translate("importer.title"))
        self.url_label.setText(translate("importer.url"))
        self.filename_label.setText(translate("importer.custom_filename"))
        self.filename_input_box.setPlaceholderText(translate("importer.custom_filename.placeholder"))
        self.filename_parts_button.setText(translate("importer.filename_parts"))
        self.log_label.setText(translate("importer.log"))
        self.instructions_label.setText(translate("importer.instructions.title"))
        self.instructions_text.setText(
            translate("importer.instructions.body", INSTRUCTIONS_TEXT, user_dir=get_settings().user_dir)
        )
        for part in DEFAULT_FILENAME_PARTS:
            self.filename_part_actions[part].setText(
                translate(f"importer.filename_part.{part.value}", FILENAME_PART_LABELS[part])
            )
        for config in _CHECKBOX_CONFIGS:
            checkbox = getattr(self, config.name)
            checkbox.setText(translate(f"importer.option.{config.setting}.label", config.label))
            checkbox.setToolTip(translate(f"importer.option.{config.setting}.tooltip", config.tooltip))
        self.generate_button.setText(translate("importer.generating" if self.is_generating else "importer.generate"))
        self._update_filename_parts_summary()
        self._update_generate_button_state()
