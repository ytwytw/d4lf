"""Searchable, catalog-backed native SNO choices."""

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from src.equipment_knowledge import EquipmentCatalog


class IdPicker(QDialog):
    def __init__(self, parent: QWidget, catalog: EquipmentCatalog, kind: str, selected: tuple[int, ...]) -> None:
        super().__init__(parent)
        self.setWindowTitle("搜索物品 / 词缀 / 类别")
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        search = QLineEdit()
        search.setPlaceholderText("输入中文、英文或 SNO ID")
        layout.addWidget(search)
        self.entries = QListWidget()
        layout.addWidget(self.entries)
        groups = {
            "type": (catalog.item_types, catalog.resolve_item_type),
            "affix": (catalog.affixes, catalog.resolve_affix),
            "unique": (catalog.items, catalog.resolve_unique),
        }
        entries, resolver = groups[kind]
        seen: set[tuple[int, ...]] = set()
        known_ids: set[int] = set()
        for entry in entries:
            if not entry.canonical_name:
                continue
            ids = resolver(entry.canonical_name)
            if not ids or ids in seen:
                continue
            seen.add(ids)
            known_ids.update(ids)
            retained = tuple(sno_id for sno_id in ids if sno_id in selected)
            label = f"{entry.name_zh or entry.name_en} · {entry.name_en} · {', '.join(map(str, ids))}"
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, retained or ids)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if retained else Qt.CheckState.Unchecked)
            self.entries.addItem(row)
        for sno_id in selected:
            if sno_id not in known_ids:
                row = QListWidgetItem(f"未知 ID {sno_id}（保留导入内容）")
                row.setData(Qt.ItemDataRole.UserRole, (sno_id,))
                row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                row.setCheckState(Qt.CheckState.Checked)
                self.entries.addItem(row)
        search.textChanged.connect(self._search)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _search(self, text: str) -> None:
        for index in range(self.entries.count()):
            row = self.entries.item(index)
            if row is not None:
                row.setHidden(text.casefold() not in row.text().casefold())

    def selected_ids(self) -> tuple[int, ...]:
        result: list[int] = []
        for index in range(self.entries.count()):
            row = self.entries.item(index)
            if row is not None and row.checkState() == Qt.CheckState.Checked:
                result.extend(row.data(Qt.ItemDataRole.UserRole))
        return tuple(dict.fromkeys(result))
