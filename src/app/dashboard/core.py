from typing import TYPE_CHECKING, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.app.dashboard.controls import ActivityLogControlsMixin
from src.app.dashboard.drag import ActivityProfileDragMixin, DragHandleButton
from src.app.dashboard.profiles import ActivityProfileRowsMixin
from src.desktop.activity import ANSIConsoleWidget
from src.desktop.widgets import CheckmarkCheckBox
from src.localization import translate
from src.settings import IS_HOTKEY_KEY, get_settings

if TYPE_CHECKING:
    from src.app.shell import UnifiedMainWindow

__all__ = ["ActivityLogWidget", "DragHandleButton"]


class ActivityLogWidget(ActivityProfileRowsMixin, ActivityProfileDragMixin, ActivityLogControlsMixin, QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = cast("UnifiedMainWindow | None", parent)
        self._config = get_settings()
        self._config.register_change_listener(self._on_config_changed)
        self.setAcceptDrops(True)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # === CENTER CONTENT: PROFILES & HOTKEYS ===
        content_hbox = QHBoxLayout()
        content_hbox.setSpacing(30)

        # -- LEFT: PROFILE LIST --
        profile_section = QVBoxLayout()
        profile_section.setSpacing(10)

        self.profile_hdr = QLabel(translate("dashboard.active_profiles"))
        self.profile_hdr.setStyleSheet("font-weight: bold; color: #888; letter-spacing: 1px;")
        profile_section.addWidget(self.profile_hdr)

        # Inline help text instead of a tooltip for better discovery and clarity
        self.profile_help = QLabel(translate("dashboard.profile_help"))
        self.profile_help.setWordWrap(True)
        self.profile_help.setObjectName("profile-help")
        profile_section.addWidget(self.profile_help)

        # Visual drop indicator for drag-and-drop
        self.drop_indicator = QFrame()
        self.drop_indicator.setObjectName("drop-indicator")
        self.drop_indicator.setFixedHeight(2)
        self.drop_indicator.hide()

        self._checkboxes: dict[str, CheckmarkCheckBox] = {}
        self._rows: dict[str, QWidget] = {}

        self.profile_scroll = QScrollArea()
        self.profile_scroll.setWidgetResizable(True)
        self.profile_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setSpacing(0)
        self.profile_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.profile_scroll.setWidget(self.profile_container)
        profile_section.addWidget(self.profile_scroll)

        # Search bar for profiles
        self.profile_search_input = QLineEdit()
        self.profile_search_input.setPlaceholderText(translate("dashboard.filter_profiles"))
        self.profile_search_input.textChanged.connect(self._filter_profiles)

        # Bulk selection buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.enable_all_btn = QPushButton(translate("dashboard.enable_all"))
        self.disable_all_btn = QPushButton(translate("dashboard.disable_all"))
        self.enable_all_btn.clicked.connect(self._select_all)
        self.disable_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(self.enable_all_btn)
        btn_layout.addWidget(self.disable_all_btn)
        btn_layout.addStretch()

        profile_section.addLayout(btn_layout)
        profile_section.addWidget(self.profile_search_input)

        content_hbox.addLayout(profile_section, stretch=6)

        # -- RIGHT: HOTKEY GRID --
        hotkey_section = QVBoxLayout()
        self.hotkey_hdr = QLabel(translate("dashboard.keyboard_shortcuts"))
        self.hotkey_hdr.setStyleSheet("font-weight: bold; color: #888; letter-spacing: 1px;")
        hotkey_section.addWidget(self.hotkey_hdr)

        self.hotkey_grid = QGridLayout()
        self.hotkey_grid.setSpacing(10)
        self._setup_hotkey_grid()

        hotkey_section.addLayout(self.hotkey_grid)
        hotkey_section.addStretch()
        content_hbox.addLayout(hotkey_section, stretch=4)

        # Use a splitter for the main dashboard content and the log viewer to allow drag-resizing
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setObjectName("dashboard-splitter")

        # Container for the dashboard content (Profiles & Hotkeys)
        top_content_container = QWidget()
        top_content_container.setLayout(content_hbox)
        self.splitter.addWidget(top_content_container)

        # === BOTTOM: MINI LOG PREVIEW ===
        self.log_viewer = ANSIConsoleWidget()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setObjectName("log-viewer")
        self.splitter.addWidget(self.log_viewer)

        # Set initial distribution (top takes priority, log starts at 100px)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([500, 100])

        self.main_layout.addWidget(self.splitter, stretch=1)

        # Hidden button that appears when the log viewer is fully collapsed
        self.show_log_btn = QPushButton(translate("dashboard.show_activity_log"))
        self.show_log_btn.setObjectName("secondary")
        self.show_log_btn.setVisible(False)
        self.main_layout.addWidget(self.show_log_btn)

        # === ACTION BAR ===
        action_layout = QHBoxLayout()
        self.import_btn = QPushButton(translate("dashboard.import_profile"))
        self.import_btn.setObjectName("primary")
        self.settings_btn = QPushButton(translate("dashboard.settings"))

        self.minimize_to_tray_cb = CheckmarkCheckBox(translate("dashboard.minimize_to_tray"))
        self.minimize_to_tray_cb.setObjectName("switch")

        for btn in [self.import_btn, self.settings_btn]:
            btn.setFixedHeight(34)
            btn.setFixedWidth(130)
            action_layout.addWidget(btn)

        self.loot_tools_btn = QPushButton("战利品工具")
        self.loot_tools_btn.setFixedHeight(34)
        tools_menu = QMenu(self.loot_tools_btn)
        if window := self._main_window:
            tools_menu.addAction("游戏过滤器生成器", lambda: window.open_native_filter())
            tools_menu.addAction("完整物品导出", window.open_inventory_dump)
            tools_menu.addAction("装备来源与词条", lambda: window.open_equipment_knowledge())
        self.loot_tools_btn.setMenu(tools_menu)
        action_layout.addWidget(self.loot_tools_btn)

        action_layout.addStretch()
        action_layout.addWidget(self.minimize_to_tray_cb)

        self.main_layout.addLayout(action_layout)
        self._connect_signals()
        self.refresh_profiles()

    def _setup_hotkey_grid(self) -> None:
        """Build the hotkey grid dynamically from AdvancedOptionsModel metadata."""
        while self.hotkey_grid.count():
            item = self.hotkey_grid.takeAt(0)
            if item is None:
                continue
            if widget := item.widget():
                widget.deleteLater()
            elif layout := item.layout():
                while layout.count():
                    child = layout.takeAt(0)
                    if child is not None and (w := child.widget()):
                        w.deleteLater()

        opts = self._config.advanced_options
        schema = opts.model_json_schema()
        properties = schema.get("properties", {})

        hotkey_items = []
        # Filter for keys that control the app (Advanced section) and are tagged as hotkeys
        for key, field in opts.model_fields.items():
            meta = field.json_schema_extra or {}
            if meta.get(IS_HOTKEY_KEY) == "True":
                val = getattr(opts, key)
                prop_meta = properties.get(key, {})
                default_label = prop_meta.get("title") or key.replace("_", " ").title()
                label = translate(f"dashboard.hotkey.{key}", default_label)
                hotkey_items.append((str(val), label))

        for i, (key_val, label) in enumerate(hotkey_items):
            row, col = divmod(i, 2)
            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(0, 0, 0, 0)
            badge = QLabel(key_val.upper())
            badge.setObjectName("key-badge")
            item_layout.addWidget(badge)
            item_layout.addWidget(QLabel(label))
            item_layout.addStretch()
            self.hotkey_grid.addLayout(item_layout, row, col)

    def retranslate_ui(self) -> None:
        self.profile_hdr.setText(translate("dashboard.active_profiles"))
        self.profile_help.setText(translate("dashboard.profile_help"))
        self.profile_search_input.setPlaceholderText(translate("dashboard.filter_profiles"))
        self.enable_all_btn.setText(translate("dashboard.enable_all"))
        self.disable_all_btn.setText(translate("dashboard.disable_all"))
        self.hotkey_hdr.setText(translate("dashboard.keyboard_shortcuts"))
        self.show_log_btn.setText(translate("dashboard.show_activity_log"))
        self.import_btn.setText(translate("dashboard.import_profile"))
        self.settings_btn.setText(translate("dashboard.settings"))
        self.minimize_to_tray_cb.setText(translate("dashboard.minimize_to_tray"))
        self._setup_hotkey_grid()
        self.refresh_profiles()
