import os
from typing import TYPE_CHECKING, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt

from src.settings import SettingsCategory
from src.settings.tab import ConfigTab

if TYPE_CHECKING:
    from src.settings.widgets import SegmentedControl


def test_config_tab_can_be_constructed(qapp, isolated_ini_loader) -> None:
    tab = ConfigTab()
    assert tab.nav_list.count() > 0
    tab.close()


def test_language_control_displays_localized_labels_but_saves_canonical_value(qapp, isolated_ini_loader) -> None:
    isolated_ini_loader.save_value("general", "language", "zhCN")
    tab = ConfigTab()
    language_control = cast("SegmentedControl", tab.model_to_parameter_value_map["general.language"])

    assert language_control.buttons["enUS"].text() == "英文"
    assert language_control.buttons["zhCN"].text() == "简体中文"

    language_control.buttons["enUS"].click()

    assert str(isolated_ini_loader.general.language) == "enUS"
    tab.close()


def test_diagnostics_page_is_hidden_until_explicitly_enabled(qapp, isolated_ini_loader) -> None:
    hidden_tab = ConfigTab()
    hidden_categories = {
        item.data(Qt.ItemDataRole.UserRole)
        for index in range(hidden_tab.nav_list.count())
        if (item := hidden_tab.nav_list.item(index)) is not None
    }
    hidden_tab.close()

    isolated_ini_loader.save_value("advanced_options", "show_diagnostics_page", True)
    visible_tab = ConfigTab()
    visible_categories = {
        item.data(Qt.ItemDataRole.UserRole)
        for index in range(visible_tab.nav_list.count())
        if (item := visible_tab.nav_list.item(index)) is not None
    }

    assert SettingsCategory.DIAGNOSTICS not in hidden_categories
    assert SettingsCategory.DIAGNOSTICS in visible_categories
    visible_tab.close()
