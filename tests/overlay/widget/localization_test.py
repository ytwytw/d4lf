from types import SimpleNamespace
from typing import Any, cast

import src.overlay.widget.localization as localization_module
from src.overlay.widget.localization import _OverlayLocalization


def test_retranslate_updates_owned_labels_and_rebuilds_open_menus(monkeypatch) -> None:
    monkeypatch.setattr(localization_module, "translate", lambda message_id: message_id)
    configured = []
    overlay = cast(
        "Any",
        SimpleNamespace(
            _closing=False,
            title=lambda text: configured.append(text),
            lbl_wb=SimpleNamespace(config=lambda **values: configured.append(values["text"])),
            lbl_legion=SimpleNamespace(config=lambda **values: configured.append(values["text"])),
            lbl_ht=SimpleNamespace(config=lambda **values: configured.append(values["text"])),
            _repack=lambda: configured.append("repacked"),
            _destroy_settings_popup=lambda: configured.append("popup-closed"),
            _close_all_submenus=lambda: configured.append("submenus-closed"),
        ),
    )

    _OverlayLocalization._retranslate_ui(overlay)

    assert configured == [
        "info.title",
        "info.timer.world_boss",
        "info.timer.legion",
        "info.timer.helltide",
        "repacked",
        "popup-closed",
        "submenus-closed",
    ]
