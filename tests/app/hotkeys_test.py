from threading import Event, Thread

from src.app.hotkeys import hotkey_signature
from src.app.interaction import GAME_INTERACTION_LOCK
from src.settings import get_settings
from tests.app.dump_runtime_test import _handler


def test_inventory_binding_participates_in_hotkey_refresh(monkeypatch) -> None:
    settings = get_settings()
    before = hotkey_signature(settings)
    monkeypatch.setattr(settings.char, "inventory", "ctrl+i")

    assert hotkey_signature(settings) != before


def test_exit_hotkey_bypasses_the_interaction_lock(mocker) -> None:
    handler = _handler(mocker)
    handler._hotkey_handles = []
    registered = {}
    mocker.patch("src.app.hotkeys.automation.add_hotkey", side_effect=lambda key, cb: registered.setdefault(key, cb))
    request = mocker.patch("src.app.hotkeys.request_exit")
    handler.setup_key_binds()
    holder_ready, release = Event(), Event()

    def hold_lock() -> None:
        with GAME_INTERACTION_LOCK:
            holder_ready.set()
            release.wait(5)

    holder = Thread(target=hold_lock)
    holder.start()
    try:
        assert holder_ready.wait(2)
        registered[handler._config.advanced_options.exit_key]()
        request.assert_called_once_with(handler)
    finally:
        release.set()
        holder.join(2)
