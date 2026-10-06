"""Keep canonical identities on editor rows instead of reverse-mapping visible text."""

from operator import itemgetter
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from collections.abc import Mapping

    from PyQt6.QtWidgets import QComboBox, QListWidgetItem

IDENTITY_ROLE = Qt.ItemDataRole.UserRole


def populate_identities(combo: QComboBox, labels: Mapping[str, str]) -> None:
    """Add one row per canonical identity, ordered by its (unique) visible label."""
    for canonical, label in sorted(labels.items(), key=itemgetter(1, 0)):
        combo.addItem(label, canonical)


def identity_for_text(combo: QComboBox, text: str) -> str | None:
    """Resolve exact visible text (selected or typed) to the identity stored on that row."""
    index = combo.findText(text, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchCaseSensitive)
    value = combo.itemData(index) if index >= 0 else None
    return value if isinstance(value, str) else None


def current_identity(combo: QComboBox) -> str | None:
    return identity_for_text(combo, combo.currentText())


def select_identity(combo: QComboBox, canonical: str) -> bool:
    index = combo.findData(canonical)
    if index >= 0:
        combo.setCurrentIndex(index)
    return index >= 0


def item_identity(item: QListWidgetItem) -> str | None:
    value = item.data(IDENTITY_ROLE)
    return value if isinstance(value, str) else None


__all__ = [
    "IDENTITY_ROLE",
    "current_identity",
    "identity_for_text",
    "item_identity",
    "populate_identities",
    "select_identity",
]
