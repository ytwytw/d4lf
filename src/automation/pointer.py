"""Direct pointer movement for observations that must not hover intermediate items."""

from src.automation.mouse import _move_mouse_abs
from src.diagnostics.safety import allow_game_input


def move_pointer_direct(x: int, y: int) -> None:
    """Move once to physical monitor pixels without synthesizing a hover path."""
    if allow_game_input("direct mouse movement"):
        _move_mouse_abs(x, y)
