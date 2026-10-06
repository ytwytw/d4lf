"""Desktop entry points for loot documents, equipment reference, and inventory export."""

from typing import TYPE_CHECKING

from src.app.dump_dialog import InventoryDumpDialog
from src.equipment_knowledge import EquipmentKnowledgeDialog
from src.native_filter import NativeFilterDialog

if TYPE_CHECKING:
    from src.app.shell import UnifiedMainWindow


class LootToolsWindows:
    def open_native_filter(self: UnifiedMainWindow, profile_name: str | None = None) -> None:
        key = f"native_filter:{profile_name or 'standalone'}"
        self._show_singleton_modal(key, NativeFilterDialog, parent=self, profile_name=profile_name)

    def open_equipment_knowledge(self: UnifiedMainWindow, profile_name: str | None = None) -> None:
        key = f"equipment_knowledge:{profile_name or 'catalog'}"
        self._show_singleton_modal(key, EquipmentKnowledgeDialog, parent=self, profile_name=profile_name)

    def open_inventory_dump(self: UnifiedMainWindow) -> None:
        self._show_singleton_modal("inventory_dump", InventoryDumpDialog, backend=self.worker, parent=self)
