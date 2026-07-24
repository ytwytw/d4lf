import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.config.profile_document import LoadedProfile
from src.config.profile_models import ProfileModel
from src.gui.profile_editor.profile_editor import ProfileEditor


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_retranslate_refreshes_catalog_backed_profile_tabs(qapp, mocker, monkeypatch) -> None:
    loaded = LoadedProfile(path=Path("profile.yaml"), name="test", profile=ProfileModel(name="test"))
    editor = ProfileEditor(loaded)
    monkeypatch.setattr("src.gui.profile_editor.profile_editor.translate_widget_tree", lambda _widget: None)
    catalog_tabs = [editor.affixes_tab, editor.charms_tab, editor.seals_tab, editor.aspect_upgrades_tab]
    refreshers = []
    for tab in catalog_tabs:
        refresher = mocker.Mock()
        tab.refresh_catalog_labels = refresher
        refreshers.append(refresher)

    editor.retranslate_ui()

    for refresher in refreshers:
        refresher.assert_called_once_with()
