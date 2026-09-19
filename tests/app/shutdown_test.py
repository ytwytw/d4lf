from threading import RLock
from types import SimpleNamespace

from src.app import shutdown
from src.app.handler import ScriptHandler


def test_script_shutdown_disables_callbacks_before_stopping_overlays(monkeypatch, mocker) -> None:
    handler = object.__new__(ScriptHandler)
    calls = []
    handler._runtime_config_lock = RLock()
    monkeypatch.setattr(
        handler,
        "_config",
        SimpleNamespace(unregister_change_listener=lambda _: calls.append("unregister")),
        raising=False,
    )
    monkeypatch.setattr(handler, "_clear_key_binds", lambda: calls.append("hotkeys"))
    monkeypatch.setattr(handler, "vision_mode", SimpleNamespace(stop=lambda: calls.append("vision")), raising=False)
    handler.loot_interaction_thread = mocker.Mock()
    handler.loot_interaction_thread.is_alive.return_value = False
    handler.paragon_overlay_thread = None
    monkeypatch.setattr(shutdown, "begin_shutdown", lambda: calls.append("input gate"))
    monkeypatch.setattr(shutdown, "request_close_paragon", lambda: calls.append("paragon"))
    monkeypatch.setattr(shutdown, "request_close", lambda: calls.append("info"))

    shutdown.shutdown_scripts(handler)

    assert handler._shutting_down
    assert calls == ["input gate", "unregister", "hotkeys", "vision", "paragon", "info"]
    handler.loot_interaction_thread.join.assert_called_once_with(timeout=2)


def test_shutdown_does_not_restart_vision_mode(mocker) -> None:
    handler = object.__new__(ScriptHandler)
    handler._shutting_down = True
    handler.vision_mode = mocker.Mock()

    handler.run_vision_mode()

    handler.vision_mode.start.assert_not_called()
