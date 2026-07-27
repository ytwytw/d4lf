from types import SimpleNamespace
from typing import Any, cast

from src.importing.gui.localization import ImporterWindowLocalization


def test_language_change_signal_only_emits_for_language_setting() -> None:
    emitted = []
    window = cast("Any", SimpleNamespace(language_changed_signal=SimpleNamespace(emit=lambda: emitted.append(True))))

    ImporterWindowLocalization._queue_language_change(window, frozenset({"general.theme"}))
    ImporterWindowLocalization._queue_language_change(window, frozenset({"general.language"}))

    assert emitted == [True]
