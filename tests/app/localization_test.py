from types import SimpleNamespace
from typing import Any, cast

import src.app.localization as localization_module
from src.app.localization import UnifiedWindowLocalization


class _Tabs:
    def __init__(self) -> None:
        self.texts = {}

    def indexOf(self, widget) -> int:  # ruff:ignore[invalid-function-name]
        return 0 if widget == "activity" else 1

    def setTabText(self, index: int, text: str) -> None:  # ruff:ignore[invalid-function-name]
        self.texts[index] = text


def test_retranslate_ui_updates_application_owned_widgets(monkeypatch) -> None:
    monkeypatch.setattr(localization_module, "translate", lambda message_id, **_values: message_id)
    window = SimpleNamespace(
        activity_tab=SimpleNamespace(retranslate_ui=lambda: None),
        console_output="console",
        exit_action=SimpleNamespace(setText=lambda text: setattr(window, "exit_text", text)),
        restore_action=SimpleNamespace(setText=lambda text: setattr(window, "restore_text", text)),
        setWindowTitle=lambda text: setattr(window, "title", text),
        tabs=_Tabs(),
        tray_icon=SimpleNamespace(setToolTip=lambda text: setattr(window, "tray_text", text)),
    )
    window.activity_tab = SimpleNamespace(retranslate_ui=lambda: setattr(window, "dashboard_retranslated", True))
    window.tabs.indexOf = lambda widget: 0 if widget is window.activity_tab else 1

    UnifiedWindowLocalization._retranslate_ui(cast("Any", window))

    assert window.title == "app.title"
    assert window.tabs.texts == {0: "tabs.dashboard", 1: "tabs.full_logs"}
    assert window.restore_text == "tray.restore"
    assert window.exit_text == "tray.exit"
    assert window.tray_text == "app.tray_title"
    assert window.dashboard_retranslated


def test_language_change_only_emits_for_language_setting() -> None:
    emitted = []
    window = SimpleNamespace(locale_changed_signal=SimpleNamespace(emit=lambda: emitted.append(True)))

    typed_window = cast("Any", window)
    UnifiedWindowLocalization._on_config_changed_language(typed_window, frozenset({"general.theme"}))
    UnifiedWindowLocalization._on_config_changed_language(typed_window, frozenset({"general.language"}))

    assert emitted == [True]
