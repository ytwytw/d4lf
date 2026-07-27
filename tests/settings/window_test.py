import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.settings.window import ICON_PATH, ConfigWindow


def test_source_mode_icon_path_points_to_repo_asset() -> None:
    expected = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
    assert expected == ICON_PATH
    assert ICON_PATH.is_file()


def test_config_window_can_be_constructed(qapp, isolated_ini_loader) -> None:
    window = ConfigWindow()
    assert window.centralWidget() is not None
    window.close()


def test_config_window_uses_current_interface_language(qapp, isolated_ini_loader) -> None:
    isolated_ini_loader.save_value("general", "language", "zhCN")

    window = ConfigWindow()

    assert window.windowTitle() == "设置"
    assert window.config_tab.search_input.placeholderText() == "搜索设置..."
    window.close()
