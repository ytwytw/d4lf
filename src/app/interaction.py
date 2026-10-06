"""Serialize admission of game interaction tasks across hotkeys and the GUI."""

from threading import RLock

GAME_INTERACTION_LOCK = RLock()
