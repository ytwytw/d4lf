"""Standalone, offline equipment browser, optionally linked to a saved profile."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.equipment_knowledge.catalog import EquipmentCatalog, load_catalog
from src.equipment_knowledge.formatting import affix_details, item_details
from src.equipment_knowledge.profile import ProfileEquipment, load_profile_equipment
from src.profiles import ProfileDocumentError


class EquipmentKnowledgeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, profile_name: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("装备资料库")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, on=True)
        self.resize(1080, 720)
        self.catalog: EquipmentCatalog | None = None
        self.profile: ProfileEquipment | None = None
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.category = QComboBox()
        self.category.addItems(["装备", "词条"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索中文、英文、规范名称、SNO 或内部 key")
        self.types = QComboBox()
        self.types.addItem("全部部位", "")
        self.profile_only = QCheckBox("仅显示此 Profile 明确指定的装备")
        self.profile_only.setEnabled(False)
        controls.addWidget(self.category)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.types)
        layout.addLayout(controls)
        layout.addWidget(self.profile_only)
        self.profile_status = QLabel("独立浏览：此资料库不会改变 Profile 或背包物品。")
        self.profile_status.setWordWrap(True)
        layout.addWidget(self.profile_status)
        splitter = QSplitter()
        self.results = QListWidget()
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        splitter.addWidget(self.results)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        try:
            self.catalog = load_catalog()
        except (OSError, ValueError) as error:
            self.status.setText(f"装备资料库不可用：{error}")
            return
        self.status.setText(
            f"离线快照 {self.catalog.data.snapshot_date} · 游戏数据 {self.catalog.game_version} · "
            f"{len(self.catalog.items)} 件具名装备 · {len(self.catalog.affixes)} 条词条记录；普通传奇获取资料尚未收录"
        )
        labels = {entry.key: entry.name_zh or entry.name_en for entry in self.catalog.item_types}
        for item_type in sorted({item.item_type for item in self.catalog.items}):
            self.types.addItem(f"{labels.get(item_type, item_type)} ({item_type})", item_type)
        if profile_name:
            try:
                self.profile = load_profile_equipment(profile_name, self.catalog)
            except (OSError, ValueError, ProfileDocumentError) as error:
                self.profile_status.setText(f"关联 Profile 失败；仍可独立浏览。{error}")
            else:
                self.profile_only.setEnabled(True)
                self.profile_only.setChecked(True)
                text = f"关联已保存 Profile：{self.profile.name} · 明确指定 {len(self.profile.unique_ids)} 个物品身份。"
                text += " 普通部位规则不代表某件暗金需求；正文替代装备未自动纳入。"
                if self.profile.unresolved:
                    text += " 未找到资料：" + "、".join(self.profile.unresolved)
                self.profile_status.setText(text)
        self.search.textChanged.connect(self.refresh)
        self.types.currentIndexChanged.connect(self.refresh)
        self.category.currentIndexChanged.connect(self.refresh)
        self.profile_only.toggled.connect(self.refresh)
        self.results.currentItemChanged.connect(self.show_current)
        self.refresh()

    def refresh(self) -> None:
        if self.catalog is None:
            return
        self.results.clear()
        self.details.clear()
        is_equipment = self.category.currentIndex() == 0
        self.types.setEnabled(is_equipment)
        self.profile_only.setEnabled(is_equipment and self.profile is not None)
        if is_equipment:
            for item in self.catalog.search(self.search.text(), self.types.currentData()):
                if self.profile_only.isChecked() and self.profile and item.sno_id not in self.profile.unique_ids:
                    continue
                row = QListWidgetItem(f"{item.name_zh or item.name_en}\n{item.name_en} · {item.sno_id}")
                row.setData(Qt.ItemDataRole.UserRole, ("item", item.sno_id))
                self.results.addItem(row)
        else:
            query = self.search.text().strip().casefold()
            for index, affix in enumerate(self.catalog.affixes):
                if query and query not in f"{affix.name_zh} {affix.name_en} {affix.key} {affix.sno_id}".casefold():
                    continue
                row = QListWidgetItem(f"{affix.name_zh or affix.name_en}\n{affix.key} · {affix.sno_id}")
                row.setData(Qt.ItemDataRole.UserRole, ("affix", index))
                self.results.addItem(row)
        if self.results.count():
            self.results.setCurrentRow(0)
        else:
            self.details.setPlainText("没有匹配记录。可清空搜索或取消 Profile 限定，查看全部离线资料。")

    def show_current(self) -> None:
        row = self.results.currentItem()
        if row is None or self.catalog is None:
            return
        kind, identity = row.data(Qt.ItemDataRole.UserRole)
        if kind == "item":
            item = next(item for item in self.catalog.items if item.sno_id == identity)
            self.details.setPlainText(item_details(item, self.catalog))
        else:
            self.details.setPlainText(affix_details(self.catalog.affixes[identity]))
