"""Game navigation limited to verified tabs, inventory opening and pure hovering."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.automation import (
    WindowSpec,
    character_inventory,
    click_pointer,
    is_window_foreground,
    move_pointer_direct,
    move_window_to_foreground,
    send_hotkey,
    stash_inventory,
)
from src.diagnostics.safety import game_input_blocked
from src.inventory_dump.layout import (
    equipment_targets,
    find_tabs,
    grid_settled,
    grid_signature,
    scale_point,
    tab_selected,
)
from src.inventory_dump.models import Location
from src.inventory_dump.reader import ScanCancelledError
from src.perception import capture, game_window_ready, is_connected, window_to_monitor
from src.settings import get_settings

if TYPE_CHECKING:
    from threading import Event

    from src.automation import Inventory, ItemSlot
    from src.inventory_dump.layout import TabTarget
    from src.type_aliases import JsonObject

# Item icons fade in after a tab switch (the filter path waits 1 s for the same reason). Occupancy is
# classified only after a minimum wait and two agreeing captures, bounded to about two seconds per page.
ICON_SETTLE_MIN = 0.6
ICON_SETTLE_POLL = 0.2
ICON_SETTLE_CAPTURES = 8


class NavigationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ScanTarget:
    location: Location
    occupied: bool | None
    favorite: bool | None = None
    junk: bool | None = None
    occupancy: JsonObject | None = None


class Navigator:
    def __init__(self, cancel: Event) -> None:
        self.cancel = cancel
        self.window = WindowSpec(get_settings().advanced_options.process_name)
        self.inventory = character_inventory()
        self.stash = stash_inventory()
        self._initial_inventory_tab: TabTarget | None = None
        self._initial_stash_tab: TabTarget | None = None

    def prepare(self) -> None:
        if self.cancel.is_set():
            raise ScanCancelledError
        if not game_window_ready() or not is_connected():
            msg = "The game window and its TTS connection must be ready before scanning."
            raise NavigationError(msg)
        if game_input_blocked():
            msg = "Game input is currently blocked by diagnostic recording or shutdown."
            raise NavigationError(msg)
        move_window_to_foreground(self.window)
        self.wait(0.3)
        self.check()
        self.neutral()
        self.wait(0.2)
        image = capture(force_new=True)
        self._initial_inventory_tab = next((tab for tab in find_tabs(image) if tab_selected(image, tab)), None)
        self._initial_stash_tab = next((tab for tab in find_tabs(image, stash=True) if tab_selected(image, tab)), None)

    def check(self) -> None:
        if self.cancel.is_set():
            raise ScanCancelledError
        if game_input_blocked():
            msg = "Game input became blocked; the partial inventory was saved."
            raise NavigationError(msg)
        if not is_window_foreground(self.window):
            msg = "The game lost focus; scanning stopped before sending further input."
            raise NavigationError(msg)
        if not is_connected():
            msg = "The TTS connection was lost."
            raise NavigationError(msg)

    def wait(self, seconds: float) -> None:
        if self.cancel.wait(seconds):
            raise ScanCancelledError

    def neutral(self) -> None:
        self.check()
        image = capture()
        self.hover(scale_point(image, 950, 80))

    def hover(self, center: tuple[int, int]) -> None:
        """Capture/layout/grid points are physical window pixels; conversion only adds window offset."""
        self.check()
        point = window_to_monitor(center)
        move_pointer_direct(int(point[0]), int(point[1]))

    def stash_tabs(self) -> list[TabTarget]:
        self.check()
        self.neutral()
        self.wait(0.2)
        tabs = find_tabs(capture(force_new=True), stash=True)
        if not tabs:
            msg = "No stash-tab controls were recognized. Open the stash before starting a complete inventory scan."
            raise NavigationError(msg)
        return tabs

    def inventory_tabs(self) -> list[TabTarget]:
        self.check()
        self.neutral()
        self.wait(0.2)
        if not find_tabs(capture(force_new=True)):
            self.check()
            send_hotkey(get_settings().char.inventory)
            for _ in range(100):
                self.wait(0.1)
                self.check()
                if find_tabs(capture(force_new=True)):
                    break
            else:
                msg = "The character inventory could not be opened."
                raise NavigationError(msg)
        self.neutral()
        self.wait(0.3)
        tabs = find_tabs(capture(force_new=True))
        if not tabs:
            msg = "Inventory category icons could not be recognized."
            raise NavigationError(msg)
        return tabs

    def select_tab(self, target: TabTarget, *, stash: bool = False) -> None:
        self.check()
        # A large equipped-item tooltip can cover the category controls until the next game frame.
        self.neutral()
        self.wait(0.2)
        image = capture(force_new=True)
        visible = find_tabs(image, stash=stash)
        if not any(
            abs(tab.center[0] - target.center[0]) < 8 and abs(tab.center[1] - target.center[1]) < 8 for tab in visible
        ):
            msg = f"Tab {target.name} is no longer visible; no click was sent."
            raise NavigationError(msg)
        if not tab_selected(image, target):
            self.hover(target.center)
            self.check()
            click_pointer("left")
            self.wait(0.35)
            self.neutral()
        for _ in range(8):
            self.check()
            if tab_selected(capture(force_new=True), target):
                return
            self.wait(0.15)
        msg = f"Tab {target.name} did not become selected; scanning this scope was stopped."
        raise NavigationError(msg)

    def grid_targets(self, page: str, *, stash: bool = False) -> list[ScanTarget]:
        self.check()
        inventory = self.stash if stash else self.inventory
        occupied, empty, settled = self._settled_slots(inventory)
        occupied_centers = {slot.center for slot in occupied}
        columns = 10 if stash else 11
        slots = sorted([*occupied, *empty], key=lambda slot: (slot.center[1], slot.center[0]))
        result = []
        for index, slot in enumerate(slots):
            row, column = index // columns + 1, index % columns + 1
            is_occupied = slot.center in occupied_centers
            result.append(
                ScanTarget(
                    Location(
                        "stash" if stash else "inventory", page, f"r{row:02d}c{column:02d}", slot.center, row, column
                    ),
                    # Pixels of still-changing icons never prove a slot empty; silence then stays unverified.
                    is_occupied if settled or is_occupied else None,
                    slot.is_fav,
                    slot.is_junk,
                    {
                        "source": "slot_screenshot_brightness",
                        "verification": "unverified",
                        "value": is_occupied,
                        "icons_settled": settled,
                    },
                )
            )
        return result

    def _settled_slots(self, inventory: Inventory) -> tuple[list[ItemSlot], list[ItemSlot], bool]:
        self.wait(ICON_SETTLE_MIN)
        previous = None
        occupied: list[ItemSlot] = []
        empty: list[ItemSlot] = []
        for capture_index in range(ICON_SETTLE_CAPTURES):
            if capture_index:
                self.wait(ICON_SETTLE_POLL)
            self.check()
            image = capture(force_new=True)
            occupied, empty = inventory.get_item_slots(image)
            current = grid_signature(image, occupied, empty)
            if previous is not None and grid_settled(previous, current):
                return occupied, empty, True
            previous = current
        return occupied, empty, False

    def equipped_targets(self, *, talisman: bool = False) -> list[ScanTarget]:
        self.check()
        self.neutral()
        self.wait(0.2)
        image = capture(force_new=True)
        return [
            ScanTarget(Location("equipped", "talisman" if talisman else "equipment", name, center), None)
            for name, center in equipment_targets(image, talisman=talisman)
        ]

    def restore(self) -> None:
        # Cancellation/shutdown never authorizes additional game input.
        if self.cancel.is_set() or game_input_blocked() or not is_window_foreground(self.window):
            return
        for target, stash in ((self._initial_inventory_tab, False), (self._initial_stash_tab, True)):
            if target is not None:
                self.select_tab(target, stash=stash)
        self.neutral()
