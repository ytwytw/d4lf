from src.app.hotkeys import hotkey_signature
from src.settings import get_settings


def test_inventory_binding_participates_in_hotkey_refresh(monkeypatch) -> None:
    settings = get_settings()
    before = hotkey_signature(settings)
    monkeypatch.setattr(settings.char, "inventory", "ctrl+i")

    assert hotkey_signature(settings) != before
