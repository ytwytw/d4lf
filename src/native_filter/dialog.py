"""Independent editor and Profile-linked native filter generation."""

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, override

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.equipment_knowledge import load_catalog
from src.native_filter.codec import encode_filter
from src.native_filter.compiler import CompilePolicy, compile_profile
from src.native_filter.decoder import decode_filter
from src.native_filter.document import SavedDocument, load_document, save_document
from src.native_filter.export import copy_code, default_directory, export_code
from src.native_filter.labels import catalog_labels, describe_condition
from src.native_filter.models import MAX_RULES, NativeFilter, NativeFilterError
from src.native_filter.rule_editor import ACTIONS, RuleDialog
from src.profiles import ProfileDocumentError, ProfileDocumentStore
from src.settings import get_settings

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


class NativeFilterDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, profile_name: str | None = None) -> None:
        super().__init__(parent)
        self.saved, self.dirty = SavedDocument(NativeFilter()), False
        self.path: Path | None = None
        self.setWindowTitle("原生游戏过滤器 — 独立编辑 / 从 Build 生成")
        self.resize(970, 730)
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        try:
            self.catalog = load_catalog()
        except (OSError, ValueError) as error:
            self.status.setText(f"原生过滤器不可用：装备资料库读取失败。\n{error}\n请重新解压完整应用后重试。")
            layout.addWidget(self.status)
            return
        self.labels = catalog_labels(self.catalog)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("关联 Profile"))
        self.profiles = QComboBox()
        source_row.addWidget(self.profiles, 1)
        refresh = QPushButton("刷新列表")
        refresh.clicked.connect(self._refresh_profiles)
        source_row.addWidget(refresh)
        generate = QPushButton("从所选 Profile 生成新副本")
        generate.clicked.connect(self._generate)
        source_row.addWidget(generate)
        layout.addLayout(source_row)
        self.drop_policy = QCheckBox("按 Build 筛选掉落装备：启用隐藏；不额外保留未解锁外观 / 圣化物品")
        self.drop_policy.setToolTip(
            "仅改变本次生成的游戏过滤器。D4LF 原有全局保护设置保持不变；关闭此选项时保守显示全部。"
        )
        layout.addWidget(self.drop_policy)
        self.name = QLineEdit()
        self.name.setPlaceholderText("过滤器名称")
        self.name.textEdited.connect(self._rename)
        layout.addWidget(self.name)
        layout.addWidget(self.status)
        self.rules = QListWidget()
        self.rules.itemDoubleClicked.connect(self._edit)
        layout.addWidget(self.rules, 2)
        actions = QHBoxLayout()
        self.edit_buttons: list[QPushButton] = []
        for label, callback in (
            ("添加规则", self._add),
            ("编辑", self._edit),
            ("删除", self._remove),
            ("上移", lambda: self._move(-1)),
            ("下移", lambda: self._move(1)),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            self.edit_buttons.append(button)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMaximumHeight(150)
        layout.addWidget(self.notes)
        self.code = QTextEdit()
        self.code.setReadOnly(True)
        self.code.setMaximumHeight(95)
        layout.addWidget(self.code)
        files = QHBoxLayout()
        for label, callback in (
            ("新建独立过滤器", self._new),
            ("导入游戏代码", self._import),
            ("打开保存文件", self._open),
            ("保存", self._save),
            ("另存为", self._save_as),
            ("复制游戏代码", lambda: copy_code(self, self.saved.document)),
            ("导出 TXT", lambda: export_code(self, self.saved.document)),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            files.addWidget(button)
        layout.addLayout(files)
        self._refresh_profiles()
        if profile_name:
            index = self.profiles.findText(profile_name)
            if index >= 0:
                self.profiles.setCurrentIndex(index)
        self._refresh()

    def _refresh_profiles(self) -> None:
        previous = self.profiles.currentText()
        self.profiles.clear()
        self.profiles.addItem("独立模式", "")
        directory = get_settings().user_dir / "profiles"
        for path in sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))):
            self.profiles.addItem(path.stem, str(path))
        index = self.profiles.findText(previous)
        if index >= 0:
            self.profiles.setCurrentIndex(index)

    def _refresh(self) -> None:
        document = self.saved.document
        index = self.rules.currentRow()
        self.name.setText(document.name)
        self.name.setReadOnly(document.opaque)
        self.rules.clear()
        for number, rule in enumerate(document.rules, 1):
            action = ACTIONS[rule.action] if 0 <= rule.action < len(ACTIONS) else f"未知动作 {rule.action}"
            conditions = "；".join(describe_condition(value, self.labels) for value in rule.conditions) or "全部物品"
            self.rules.addItem(f"{number}. {'✓' if rule.enabled else '○'} {rule.name} — {action}\n    {conditions}")
        if index >= 0:
            self.rules.setCurrentRow(min(index, len(document.rules) - 1))
        for button in self.edit_buttons:
            button.setEnabled(not document.opaque)
        state = "包含启用的隐藏规则，请检查规则顺序" if document.hides_items else "当前不会隐藏物品"
        if document.opaque:
            state = "含未知字段：只读保护，原码无损导出；显示的条件可能不完整"
        association = f" · 来源 Profile：{self.saved.profile_name}" if self.saved.profile_name else " · 独立模式"
        self.status.setText(
            f"{len(document.rules)}/{MAX_RULES} 条规则 · {state}{association}\n从上到下，先匹配规则优先。"
            + (" · 有未保存修改" if self.dirty else "")
        )
        self.notes.setPlainText(
            "\n".join(self.saved.warnings) or "可自由编排规则。没有条件的规则匹配全部物品；请将兜底规则放在最后。"
        )
        try:
            self.code.setPlainText(encode_filter(document))
        except NativeFilterError as error:
            self.code.setPlainText(f"无法导出：{error}")

    def _allow_replace(self) -> bool:
        if not self.dirty:
            return True
        return (
            QMessageBox.question(
                self,
                "保留当前修改",
                "当前有未保存修改。放弃这些修改并继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _changed(self) -> None:
        self.dirty = True
        self.saved.manually_edited = True
        self._refresh()

    def _rename(self, name: str) -> None:
        self.saved.document.name = name
        self._changed()

    def _new(self) -> None:
        if self._allow_replace():
            self.saved, self.path, self.dirty = SavedDocument(NativeFilter()), None, False
            self._refresh()

    def _generate(self) -> None:
        source = self.profiles.currentData()
        if not source:
            QMessageBox.information(self, "选择 Profile", "请选择一个 Profile，或使用新建独立过滤器。")
            return
        if not self._allow_replace():
            return
        try:
            profile = ProfileDocumentStore.default().load(Path(source)).profile
            policy = CompilePolicy.from_settings(get_settings().general)
            if self.drop_policy.isChecked():
                policy = replace(policy, handle_cosmetics="junk", preserve_sanctified=False)
            result = compile_profile(profile, self.catalog, policy)
            warnings = result.warnings
            if self.drop_policy.isChecked():
                warnings += (
                    "已选择掉落筛选策略：没有额外的未知外观 / 圣化保护；只改变此游戏过滤器，不改变 D4LF 设置。",
                )
            self.saved = SavedDocument(
                result.document, result.profile_name, result.profile_digest, result.game_version, warnings
            )
            self.saved.source, self.saved.generation_policy = profile.source, policy
            self.path, self.dirty = None, True
            self._refresh()
        except (OSError, ValueError, ProfileDocumentError) as error:
            QMessageBox.warning(self, "生成失败", str(error))

    def _add(self) -> None:
        if len(self.saved.document.rules) >= MAX_RULES:
            QMessageBox.warning(self, "规则上限", "游戏最多支持 25 条规则。")
            return
        dialog = RuleDialog(self, self.catalog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.saved.document.rules.insert(max(0, self.rules.currentRow()), dialog.rule)
            self._changed()

    def _edit(self) -> None:
        index = self.rules.currentRow()
        if index < 0 or self.saved.document.opaque:
            return
        dialog = RuleDialog(self, self.catalog, self.saved.document.rules[index])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.saved.document.rules[index] = dialog.rule
            self._changed()

    def _remove(self) -> None:
        index = self.rules.currentRow()
        if index >= 0 and len(self.saved.document.rules) > 1:
            self.saved.document.rules.pop(index)
            self._changed()

    def _move(self, delta: int) -> None:
        index = self.rules.currentRow()
        target = index + delta
        if 0 <= index < len(self.saved.document.rules) and 0 <= target < len(self.saved.document.rules):
            rules = self.saved.document.rules
            rules[index], rules[target] = rules[target], rules[index]
            self.rules.setCurrentRow(target)
            self._changed()

    def _import(self) -> None:
        if not self._allow_replace():
            return
        code, accepted = QInputDialog.getMultiLineText(self, "导入游戏代码", "粘贴完整游戏过滤器代码")
        if accepted:
            try:
                self.saved = SavedDocument(decode_filter(code))
                self.path, self.dirty = None, True
                self._refresh()
            except NativeFilterError as error:
                QMessageBox.warning(self, "导入失败", str(error))

    def _open(self) -> None:
        if not self._allow_replace():
            return
        try:
            path, _ = QFileDialog.getOpenFileName(self, "打开过滤器", str(default_directory()), "D4LF 过滤器 (*.json)")
            if path:
                self.saved, self.path, self.dirty = load_document(Path(path)), Path(path), False
                self._refresh()
        except (OSError, NativeFilterError) as error:
            QMessageBox.warning(self, "打开失败", str(error))

    def _save(self) -> None:
        if self.path is None:
            self._save_as()
            return
        try:
            save_document(self.path, self.saved)
            self.dirty = False
            self._refresh()
        except (OSError, NativeFilterError) as error:
            QMessageBox.warning(self, "保存失败", str(error))

    def _save_as(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存独立过滤器", str(default_directory() / "filter.json"), "D4LF 过滤器 (*.json)"
            )
            if path:
                self.path = Path(path)
                self._save()
        except OSError as error:
            QMessageBox.warning(self, "保存失败", str(error))

    @override
    def reject(self) -> None:
        if self._allow_replace():
            super().reject()
