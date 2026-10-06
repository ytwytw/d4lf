"""Rule dialog with explicit action and conjunctive conditions."""

from copy import deepcopy
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.native_filter.codec import validate_document
from src.native_filter.condition_editor import ConditionDialog
from src.native_filter.labels import catalog_labels, describe_condition
from src.native_filter.models import NativeFilter, NativeFilterError, Rule

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from src.equipment_knowledge import EquipmentCatalog

ACTIONS = ("显示", "隐藏文字", "改色", "完全隐藏")


class RuleDialog(QDialog):
    def __init__(self, parent: QWidget, catalog: EquipmentCatalog, rule: Rule | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.labels = catalog_labels(catalog)
        self.rule = deepcopy(rule or Rule())
        self.setWindowTitle("编辑规则 — 条件同时满足")
        self.resize(710, 480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.rule.name)
        self.action = QComboBox()
        self.action.addItems(ACTIONS)
        self.action.setCurrentIndex(int(self.rule.action))
        self.color = QLineEdit(self.rule.color_hex)
        self.enabled = QCheckBox("启用规则")
        self.enabled.setChecked(self.rule.enabled)
        for label, widget in (
            ("名称", self.name),
            ("动作", self.action),
            ("颜色 #RRGGBB", self.color),
            ("", self.enabled),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        self.conditions = QListWidget()
        layout.addWidget(self.conditions)
        controls = QHBoxLayout()
        for text, callback in (("添加条件", self._add), ("编辑条件", self._edit), ("删除条件", self._remove)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls.addWidget(button)
        layout.addLayout(controls)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.conditions.itemDoubleClicked.connect(self._edit)
        self._refresh()

    def _refresh(self) -> None:
        self.conditions.clear()
        self.conditions.addItems([describe_condition(condition, self.labels) for condition in self.rule.conditions])

    def _add(self) -> None:
        self._condition_dialog(None)

    def _edit(self) -> None:
        index = self.conditions.currentRow()
        if index >= 0:
            self._condition_dialog(index)

    def _condition_dialog(self, index: int | None) -> None:
        existing = None if index is None else self.rule.conditions[index]
        dialog = ConditionDialog(self, self.catalog, existing)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_condition is not None:
            condition = dialog.result_condition
            if any(value.kind == condition.kind for i, value in enumerate(self.rule.conditions) if i != index):
                QMessageBox.warning(self, "条件重复", "游戏中同一规则不能重复添加相同条件类型。")
                return
            if index is None:
                self.rule.conditions.append(condition)
            else:
                self.rule.conditions[index] = condition
            self._refresh()

    def _remove(self) -> None:
        index = self.conditions.currentRow()
        if index >= 0:
            self.rule.conditions.pop(index)
            self._refresh()

    def _accept(self) -> None:
        self.rule.name = self.name.text()
        self.rule.action = self.action.currentIndex()
        self.rule.color_hex = self.color.text().strip()
        self.rule.enabled = self.enabled.isChecked()
        try:
            validate_document(NativeFilter(rules=[self.rule]))
        except NativeFilterError as error:
            QMessageBox.warning(self, "规则无效", str(error))
            return
        self.accept()
