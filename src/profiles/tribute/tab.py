from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.profiles import TributeFilterModel
from src.profiles.editor.identity import IDENTITY_ROLE, item_identity
from src.profiles.editor.pickers import RarityPicker, rarity_summary
from src.profiles.labels import tribute_labels
from src.profiles.tribute.dialogs import CreateTribute

TRIBUTES_TABNAME = "Tributes"
_TRIBUTE_PREFIX = "Tribute: "


class TributesTab(QWidget):
    def __init__(self, tributes: TributeFilterModel | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tributes = tributes if tributes is not None else TributeFilterModel()
        self.list_widget = QListWidget()
        self.rarity_line_edit = QLineEdit()
        self.loaded = False

    def load(self) -> None:
        if not self.loaded:
            self.setup_ui()
            self.loaded = True

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 20, 0, 20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        label = QLabel(
            "Add tribute names and select rarities you want to keep. Leaving rarities empty keeps all rarities."
        )
        label.setWordWrap(True)
        main_layout.addWidget(label)

        button_layout = QHBoxLayout()
        add_tribute_button = QPushButton("Add Tribute")
        add_tribute_button.clicked.connect(self._add_tribute)
        button_layout.addWidget(add_tribute_button)

        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected)
        button_layout.addWidget(remove_button)
        main_layout.addLayout(button_layout)

        self.rarity_line_edit.setReadOnly(True)
        self.refresh_rarity_summary()
        rarity_layout = QHBoxLayout()
        rarity_layout.addWidget(self.rarity_line_edit)
        edit_rarities_button = QPushButton("...")
        edit_rarities_button.setMaximumWidth(40)
        edit_rarities_button.clicked.connect(self.edit_rarities)
        rarity_layout.addWidget(edit_rarities_button)
        rarity_layout.addStretch()
        rarity_form = QFormLayout()
        rarity_form.addRow("Rarities:", rarity_layout)
        main_layout.addLayout(rarity_form)

        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._reload_list_widget()
        main_layout.addWidget(self.list_widget)
        self.setLayout(main_layout)

    def _reload_list_widget(self) -> None:
        self.list_widget.clear()
        labels = tribute_labels()
        for tribute_name in self.tributes.name:
            item = QListWidgetItem(f"{_TRIBUTE_PREFIX}{labels.get(tribute_name, tribute_name)}")
            item.setData(IDENTITY_ROLE, tribute_name)
            self.list_widget.addItem(item)

    def _add_tribute(self) -> None:
        dialog = CreateTribute(self.tributes.name)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            value = dialog.get_value()
            for tribute_name in value.name:
                if tribute_name not in self.tributes.name:
                    self.tributes.name.append(tribute_name)
            self._reload_list_widget()

    def refresh_rarity_summary(self) -> None:
        self.rarity_line_edit.setText(rarity_summary(self.tributes.rarities))

    def edit_rarities(self) -> None:
        picker = RarityPicker(self, self.tributes.rarities)
        if picker.exec() == QDialog.DialogCode.Accepted:
            self.tributes.rarities = picker.get_selected_rarities()
            self.refresh_rarity_summary()

    def remove_selected(self) -> None:
        rows = sorted({self.list_widget.row(item) for item in self.list_widget.selectedItems()}, reverse=True)
        if not rows:
            QMessageBox.warning(self, "Warning", "Select at least one tribute rule to remove.")
            return

        for row in rows:
            item = self.list_widget.item(row)
            tribute_name = item_identity(item) if item is not None else None
            if tribute_name in self.tributes.name:
                self.tributes.name.remove(tribute_name)

        self._reload_list_widget()
