from types import SimpleNamespace
from typing import Any, cast

import src.paragon.overlay.localization as localization_module
from src.paragon.overlay.localization import OverlayLocalizationMixin


def test_live_language_change_retranslates_and_rebuilds_locale_content(monkeypatch) -> None:
    monkeypatch.setattr(localization_module, "is_alive", lambda _overlay: True)
    monkeypatch.setattr(localization_module, "translate", lambda message_id: message_id)
    configured = []
    overlay = cast(
        "Any",
        SimpleNamespace(
            _cfg=SimpleNamespace(is_collapsed=True),
            title=lambda text: configured.append(("title", text)),
            lbl_mode=SimpleNamespace(config=lambda **values: configured.append(("mode", values["text"]))),
            btn_settings=SimpleNamespace(config=lambda **values: configured.append(("settings", values["text"]))),
            btn_build_menu=SimpleNamespace(config=lambda **values: configured.append(("builds", values["text"]))),
            _settings_popup=None,
            _settings_popup_refresh=object(),
            _close_build_dropdown=lambda: configured.append("build-closed"),
            _close_settings_dropdown=lambda: configured.append("settings-closed"),
            _refresh_lists=lambda: configured.append("refreshed"),
            redraw=lambda: configured.append("redrawn"),
        ),
    )

    OverlayLocalizationMixin._apply_live_language_change(overlay)

    assert configured == [
        ("title", "paragon.title"),
        ("mode", "paragon.view.compact"),
        ("settings", "paragon.settings⚙ ▼"),
        ("builds", "paragon.builds ▼"),
        "build-closed",
        "settings-closed",
        "refreshed",
        "redrawn",
    ]
    assert overlay._settings_popup_refresh is None
