"""Structured editor for all ten known native game conditions."""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.native_filter.codec import validate_condition
from src.native_filter.labels import LABELS, PROPERTIES, RARITIES, catalog_labels, id_labels
from src.native_filter.models import Condition, ConditionKind, NativeFilterError
from src.native_filter.picker import IdPicker

if TYPE_CHECKING:
    from src.equipment_knowledge import EquipmentCatalog


def parse_ids(text: str) -> tuple[int, ...]:
    try:
        values = tuple(
            dict.fromkeys(int(part) for part in text.replace("，", ",").replace(" ", ",").split(",") if part)
        )
    except ValueError as error:
        msg = "SNO ID 必须为逗号分隔的整数"
        raise NativeFilterError(msg) from error
    if any(not 0 < value < 1 << 32 for value in values):
        msg = "SNO ID 必须为 1–4294967295"
        raise NativeFilterError(msg)
    return values


class ConditionDialog(QDialog):
    def __init__(self, parent: QWidget, catalog: EquipmentCatalog, condition: Condition | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.labels = catalog_labels(catalog)
        self.result_condition: Condition | None = None
        self.setWindowTitle("编辑条件")
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.kind = QComboBox()
        for value, label in LABELS.items():
            self.kind.addItem(label, value.value)
        self.form.addRow("条件", self.kind)
        self.minimum, self.maximum = QLineEdit(), QLineEdit()
        self.form.addRow("最低强度（空=不限）", self.minimum)
        self.form.addRow("最高强度（空=不限）", self.maximum)
        self.mask_choices = QWidget()
        self.mask_layout = QVBoxLayout(self.mask_choices)
        self.mask_checks: dict[int, QCheckBox] = {}
        self.form.addRow("匹配任一项", self.mask_choices)
        self.ids, self.ga_ids, self.piece_ids, self.set_id = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        self.selection = QLabel("尚未选择")
        self.selection.setWordWrap(True)
        self.form.addRow("已选择", self.selection)
        self.form.addRow("SNO ID（逗号分隔）", self.ids)
        self.choose = QPushButton("从资料库选择…")
        self.form.addRow("", self.choose)
        self.choose.clicked.connect(self._choose)
        self.ids.textChanged.connect(self._selection_changed)
        self.advanced = QCheckBox("高级：直接编辑 SNO ID")
        self.advanced.toggled.connect(self._update_fields)
        self.form.addRow("", self.advanced)
        self.count = QSpinBox()
        self.count.setRange(0, 999)
        self.count.setValue(1)
        self.form.addRow("至少几条", self.count)
        self.form.addRow("其中须为 GA 的词缀 ID", self.ga_ids)
        self.choose_ga = QPushButton("选择须为大词缀的词缀…")
        self.form.addRow("", self.choose_ga)
        self.choose_ga.clicked.connect(self._choose_ga)
        self.form.addRow("套装 SNO ID", self.set_id)
        self.form.addRow("套装部件 ID", self.piece_ids)
        self.help = QLabel()
        self.help.setWordWrap(True)
        layout.addWidget(self.help)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self._update_fields)
        if condition is not None:
            self.kind.setCurrentIndex(self.kind.findData(condition.kind.value))
            self.minimum.setText("" if condition.minimum is None else str(condition.minimum))
            self.maximum.setText("" if condition.maximum is None else str(condition.maximum))
            self.ids.setText(", ".join(map(str, condition.sno_ids)))
            self.ga_ids.setText(", ".join(map(str, condition.ga_sno_ids)))
            if condition.ga_sno_ids:
                self.choose_ga.setText("须为大词缀：" + id_labels(condition.ga_sno_ids, self.labels))
            self.piece_ids.setText(", ".join(map(str, condition.piece_sno_ids)))
            self.set_id.setText("" if condition.set_sno_id is None else str(condition.set_sno_id))
            self.count.setValue(condition.min_count)
        self._update_fields()
        if condition is not None:
            for value, check in self.mask_checks.items():
                check.setChecked(bool(condition.mask & value))

    def _update_fields(self) -> None:
        kind = ConditionKind(self.kind.currentData())
        affixes = kind in {ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}
        ids = affixes or kind in {ConditionKind.ITEM_TYPES, ConditionKind.SPECIFIC_ITEMS}
        self.form.setRowVisible(self.minimum, kind == ConditionKind.ITEM_POWER)
        self.form.setRowVisible(self.maximum, kind == ConditionKind.ITEM_POWER)
        self.form.setRowVisible(self.mask_choices, kind in {ConditionKind.RARITY, ConditionKind.PROPERTIES})
        choices = RARITIES if kind == ConditionKind.RARITY else PROPERTIES
        if set(self.mask_checks) != set(choices):
            while self.mask_layout.count():
                item = self.mask_layout.takeAt(0)
                if item is not None and (widget := item.widget()) is not None:
                    widget.deleteLater()
            self.mask_checks = {value: QCheckBox(label) for value, label in choices.items()}
            for check in self.mask_checks.values():
                self.mask_layout.addWidget(check)
        self.form.setRowVisible(self.ids, ids and self.advanced.isChecked())
        self.form.setRowVisible(self.selection, ids)
        self.form.setRowVisible(self.advanced, ids)
        self.form.setRowVisible(self.choose, ids)
        self.form.setRowVisible(self.count, affixes or kind == ConditionKind.GREATER_AFFIX)
        self.form.setRowVisible(self.ga_ids, affixes and self.advanced.isChecked())
        self.form.setRowVisible(self.choose_ga, affixes)
        self.form.setRowVisible(self.set_id, kind == ConditionKind.TALISMAN_SET)
        self.form.setRowVisible(self.piece_ids, kind == ConditionKind.TALISMAN_SET)
        texts = {
            ConditionKind.RARITY: "可相加：白=1，蓝=2，黄=4，传奇=8，暗金=16，神话=32，套装护符=64。",
            ConditionKind.PROPERTIES: "已知标记：普通=1，先祖=4，神话=32。可相加。",
            ConditionKind.CODEX: "匹配可解锁或升级力量法典的物品，无其他参数。",
            ConditionKind.TALISMAN_SET: "使用已核验的套装及物品 SNO ID；套装资料映射尚未自动提供。",
        }
        self.help.setText(texts.get(kind, "同一规则中的条件同时满足；列表中的 ID 表示可选目标。"))

    def _selection_changed(self) -> None:
        try:
            self.selection.setText(id_labels(parse_ids(self.ids.text()), self.labels) or "尚未选择")
        except NativeFilterError:
            self.selection.setText("请修正高级 ID 输入")

    def _choose_ga(self) -> None:
        try:
            dialog = IdPicker(self, self.catalog, "affix", parse_ids(self.ga_ids.text()))
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ids = tuple(value for value in dialog.selected_ids() if value in parse_ids(self.ids.text()))
                self.ga_ids.setText(", ".join(map(str, ids)))
                self.choose_ga.setText("须为大词缀：" + (id_labels(ids, self.labels) or "未选择"))
        except NativeFilterError as error:
            QMessageBox.warning(self, "条件无效", str(error))

    def _choose(self) -> None:
        kind = ConditionKind(self.kind.currentData())
        mode = (
            "type"
            if kind == ConditionKind.ITEM_TYPES
            else "unique"
            if kind == ConditionKind.SPECIFIC_ITEMS
            else "affix"
        )
        try:
            dialog = IdPicker(self, self.catalog, mode, parse_ids(self.ids.text()))
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.ids.setText(", ".join(map(str, dialog.selected_ids())))
        except NativeFilterError as error:
            QMessageBox.warning(self, "条件无效", str(error))

    def _accept(self) -> None:
        try:
            kind = ConditionKind(self.kind.currentData())
            condition = Condition(kind)
            if kind == ConditionKind.ITEM_POWER:
                condition.minimum = int(self.minimum.text()) if self.minimum.text().strip() else None
                condition.maximum = int(self.maximum.text()) if self.maximum.text().strip() else None
            if kind in {ConditionKind.RARITY, ConditionKind.PROPERTIES}:
                condition.mask = sum(value for value, check in self.mask_checks.items() if check.isChecked())
            if kind in {
                ConditionKind.ITEM_TYPES,
                ConditionKind.SPECIFIC_ITEMS,
                ConditionKind.REQUIRED_AFFIXES,
                ConditionKind.OPTIONAL_AFFIXES,
            }:
                condition.sno_ids = parse_ids(self.ids.text())
            if kind in {ConditionKind.GREATER_AFFIX, ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
                condition.min_count = self.count.value()
            if kind in {ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
                condition.ga_sno_ids = parse_ids(self.ga_ids.text())
            if kind == ConditionKind.TALISMAN_SET:
                condition.set_sno_id = int(self.set_id.text())
                condition.piece_sno_ids = parse_ids(self.piece_ids.text())
            validate_condition(condition)
        except (ValueError, NativeFilterError) as error:
            QMessageBox.warning(self, "条件无效", str(error))
            return
        self.result_condition = condition
        self.accept()
