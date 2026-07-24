from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.loader import PARAMS_INI, IniConfigLoader
from src.config.settings_models import CATEGORY_KEY, HIDE_FROM_GUI_KEY, GeneralModel, SettingsCategory
from src.gui.i18n import EN_US, ZH_CN, language_label, translate, translate_widget_tree
from src.gui.models.dialog import CreateUnique, DeleteAffixPool
from src.gui.settings_tab import ConfigTab, SegmentedControl

if TYPE_CHECKING:
    from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def isolated_ini_loader(tmp_path: Path):
    loader = IniConfigLoader()
    original_user_dir = loader._user_dir
    original_parser = loader._parser
    original_general = loader._general
    original_char = loader._char
    original_advanced_options = loader._advanced_options
    original_signature = loader._last_config_signature
    original_revision = loader._config_revision
    original_listeners = list(loader._change_listeners)
    original_deferred_cleanup_logs = list(loader._deferred_cleanup_log_records)
    original_defer_cleanup_logs = loader._defer_cleanup_log_records

    loader._user_dir = tmp_path
    loader._change_listeners = []
    loader._deferred_cleanup_log_records = []
    loader._defer_cleanup_log_records = True
    loader.load(clear=True)

    try:
        yield loader
    finally:
        loader._user_dir = original_user_dir
        loader._parser = original_parser
        loader._general = original_general
        loader._char = original_char
        loader._advanced_options = original_advanced_options
        loader._last_config_signature = original_signature
        loader._config_revision = original_revision
        loader._change_listeners = original_listeners
        loader._deferred_cleanup_log_records = original_deferred_cleanup_logs
        loader._defer_cleanup_log_records = original_defer_cleanup_logs


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_translate_supports_static_and_rendered_template_round_trips() -> None:
    assert translate("Settings", locale=ZH_CN) == "设置"
    assert translate("设置", locale=EN_US) == "Settings"

    english_title = "D4LF - Diablo 4 Loot Filter v1.2.3"
    chinese_title = "D4LF - 暗黑破坏神 IV 装备过滤器 v1.2.3"
    assert translate(english_title, locale=ZH_CN) == chinese_title
    assert translate(chinese_title, locale=EN_US) == english_title

    assert language_label(EN_US, locale=ZH_CN) == "英文 (enUS)"
    assert language_label(ZH_CN, locale=EN_US) == "Simplified Chinese (zhCN)"


def test_info_overlay_and_interaction_status_text_is_fully_localized() -> None:
    expected = {
        "World Boss:": "世界首领：",
        "GPH:": "金币/小时：",
        "Pending": "等待采集",
        "Ready": "就绪",
        "Vision Mode: Disabled (GUI-only)": "视觉模式：已禁用（仅 GUI）",
        "TTS: Disabled (GUI-only)": "TTS：已禁用（仅 GUI）",
        "Unknown capture error": "未知采集错误",
    }

    for english, chinese in expected.items():
        assert translate(english, locale=ZH_CN) == chinese
        assert translate(chinese, locale=EN_US) == english


def test_translate_widget_tree_preserves_stable_control_values(qapp) -> None:
    root = QWidget()
    layout = QVBoxLayout(root)
    label = QLabel("Settings")
    button = QPushButton("Reset to defaults")
    button.setToolTip("Reset Settings")
    checkbox = QCheckBox("Auto Sync")
    summary = QLineEdit("All rarities")
    summary.setReadOnly(True)
    combo = QComboBox()
    combo.setProperty("translate_items", True)
    combo.addItem("dark", "dark")
    combo.addItem("light", "light")
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Unique Rule 2")

    for widget in (label, button, checkbox, summary, combo, tabs):
        layout.addWidget(widget)

    translate_widget_tree(root, locale=ZH_CN)

    assert label.text() == "设置"
    assert button.text() == "恢复默认值"
    assert button.toolTip() == "重置设置"
    assert checkbox.text() == "自动同步"
    assert summary.text() == "全部稀有度"
    assert [combo.itemText(index) for index in range(combo.count())] == ["深色", "浅色"]
    assert [combo.itemData(index) for index in range(combo.count())] == ["dark", "light"]
    assert tabs.tabText(0) == "暗金规则 2"

    translate_widget_tree(root, locale=EN_US)

    assert label.text() == "Settings"
    assert button.text() == "Reset to defaults"
    assert checkbox.text() == "Auto Sync"
    assert summary.text() == "All rarities"
    assert [combo.itemText(index) for index in range(combo.count())] == ["dark", "light"]
    assert [combo.itemData(index) for index in range(combo.count())] == ["dark", "light"]
    assert tabs.tabText(0) == "Unique Rule 2"
    root.close()


def test_language_setting_is_visible_and_controls_interface_and_game_locale() -> None:
    metadata = GeneralModel.model_json_schema()["properties"]["language"]

    assert metadata["title"] == "Interface and Game Language"
    assert metadata[CATEGORY_KEY] == SettingsCategory.SYSTEM
    assert not metadata.get(HIDE_FROM_GUI_KEY)


def test_automatic_failure_capture_setting_is_visible_and_defaults_off() -> None:
    metadata = GeneralModel.model_json_schema()["properties"]["automatic_failure_capture"]

    assert GeneralModel().automatic_failure_capture is False
    assert metadata["title"] == "Automatic Failure Capture"
    assert metadata[CATEGORY_KEY] == SettingsCategory.ADVANCED
    assert not metadata.get(HIDE_FROM_GUI_KEY)


def test_diagnostics_tab_setting_is_visible_and_defaults_off() -> None:
    metadata = GeneralModel.model_json_schema()["properties"]["show_diagnostics_tab"]

    assert GeneralModel().show_diagnostics_tab is False
    assert metadata["title"] == "Show Diagnostic Capture Tab"
    assert metadata[CATEGORY_KEY] == SettingsCategory.ADVANCED
    assert not metadata.get(HIDE_FROM_GUI_KEY)


def test_config_tab_can_enable_automatic_failure_capture(qapp, isolated_ini_loader: IniConfigLoader) -> None:
    tab = ConfigTab()
    qapp.processEvents()
    control = tab.model_to_parameter_value_map["general.automatic_failure_capture"]

    assert control.isChecked() is False
    control.click()

    assert isolated_ini_loader.general.automatic_failure_capture is True
    assert "automatic_failure_capture = True" in (isolated_ini_loader.user_dir / PARAMS_INI).read_text(encoding="utf-8")
    tab.close()


def test_config_tab_can_enable_diagnostics_tab(qapp, isolated_ini_loader: IniConfigLoader) -> None:
    tab = ConfigTab()
    qapp.processEvents()
    control = tab.model_to_parameter_value_map["general.show_diagnostics_tab"]

    assert control.isChecked() is False
    control.click()

    assert isolated_ini_loader.general.show_diagnostics_tab is True
    assert "show_diagnostics_tab = True" in (isolated_ini_loader.user_dir / PARAMS_INI).read_text(encoding="utf-8")
    tab.close()


def test_translated_dialog_checkboxes_return_stable_business_values(qapp) -> None:
    delete_dialog = DeleteAffixPool(2)
    translate_widget_tree(delete_dialog, locale=ZH_CN)
    delete_dialog.checkbox_list[0].setChecked(True)

    assert delete_dialog.checkbox_list[0].text() == "第 0 组"
    assert delete_dialog.get_value() == ["Count 0"]

    unique_dialog = CreateUnique()
    translate_widget_tree(unique_dialog, locale=ZH_CN)
    for checkbox in unique_dialog.checkbox_list:
        checkbox.setChecked(True)

    assert [checkbox.text() for checkbox in unique_dialog.checkbox_list] == ["威能", "词缀"]
    assert unique_dialog.get_value() == ["Aspect", "Affixes"]
    delete_dialog.close()
    unique_dialog.close()


def test_config_tab_language_switch_persists_stable_locale_code(qapp, isolated_ini_loader: IniConfigLoader) -> None:
    callbacks: list[str] = []
    tab = ConfigTab(language_changed_callback=lambda: callbacks.append(isolated_ini_loader.general.language))
    qapp.processEvents()

    control = tab.model_to_parameter_value_map["general.language"]
    assert isinstance(control, SegmentedControl)
    assert control.buttons[EN_US].text() == "English (enUS)"
    assert control.buttons[ZH_CN].property("option_value") == ZH_CN

    control.buttons[ZH_CN].click()

    assert isolated_ini_loader.general.language == ZH_CN
    assert callbacks == [ZH_CN]
    assert "language = zhCN" in (isolated_ini_loader.user_dir / PARAMS_INI).read_text(encoding="utf-8")

    tab.close()
    qapp.processEvents()

    chinese_tab = ConfigTab(language_changed_callback=lambda: callbacks.append(isolated_ini_loader.general.language))
    qapp.processEvents()
    chinese_control = chinese_tab.model_to_parameter_value_map["general.language"]
    assert isinstance(chinese_control, SegmentedControl)
    assert chinese_control.buttons[EN_US].text() == "英文 (enUS)"
    assert chinese_control.buttons[ZH_CN].text() == "简体中文 (zhCN)"
    nav_labels = [
        item.text()
        for index in range(chinese_tab.nav_list.count())
        if (item := chinese_tab.nav_list.item(index)) is not None
    ]
    assert "⚙️ 系统与路径" in nav_labels

    chinese_control.buttons[EN_US].click()
    assert isolated_ini_loader.general.language == EN_US
    assert callbacks == [ZH_CN, EN_US]
    chinese_tab.close()
