import os
from typing import TYPE_CHECKING, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
