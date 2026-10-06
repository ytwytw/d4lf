from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture
def native_app(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    settings = SimpleNamespace(
        user_dir=tmp_path,
        general=SimpleNamespace(
            filter_equipment=True, keep_aspects="upgrade", handle_uniques="favorite", handle_cosmetics="ignore"
        ),
    )
    monkeypatch.setattr("src.native_filter.dialog.get_settings", lambda: settings)
    monkeypatch.setattr("src.native_filter.export.get_settings", lambda: settings)
    return app
