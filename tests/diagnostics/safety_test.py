import src.diagnostics.safety as safety_module


def test_manual_capture_blocks_game_input(monkeypatch) -> None:
    monkeypatch.setattr(safety_module, "is_diagnostic_capture_active", lambda: True)

    assert safety_module.game_input_blocked()
    assert not safety_module.allow_game_input("mouse click")


def test_automatic_capture_does_not_participate_in_the_input_gate(monkeypatch) -> None:
    monkeypatch.setattr(safety_module, "is_diagnostic_capture_active", lambda: False)

    assert safety_module.allow_game_input("mouse click")
