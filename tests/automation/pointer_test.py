from src.automation import move_pointer_direct


def test_direct_pointer_sends_one_destination_without_hovering_intermediate_points(mocker) -> None:
    mocker.patch("src.automation.pointer.allow_game_input", return_value=True)
    move = mocker.patch("src.automation.pointer._move_mouse_abs")
    move_pointer_direct(3255, 1525)
    move.assert_called_once_with(3255, 1525)


def test_direct_pointer_obeys_game_input_safety_gate(mocker) -> None:
    mocker.patch("src.automation.pointer.allow_game_input", return_value=False)
    move = mocker.patch("src.automation.pointer._move_mouse_abs")
    move_pointer_direct(3255, 1525)
    move.assert_not_called()
