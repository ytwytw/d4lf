import os
from types import SimpleNamespace
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from src.gui.models import activity_log_widget, catalog_display
from src.gui.models.activity_log_widget import ActivityLogWidget, DragHandleButton
from src.item.data.item_type import ItemType


def test_drag_handle_forwards_mouse_events():
    _app = QApplication.instance() or QApplication([])
    row_widget = QWidget()
    received: list[tuple[object, QWidget, QWidget]] = []

    def start_drag(event: object, row: QWidget, handle: QWidget) -> None:
        received.append((event, row, handle))

    drag_handle = DragHandleButton(row_widget, start_drag)
    drag_handle.mouseMoveEvent(None)

    assert received == [(None, row_widget, drag_handle)]


def test_profile_summary_localizes_item_types_without_changing_profile_model(tmp_path, monkeypatch):
    path = tmp_path / "profile.yaml"
    path.write_text("name: test", encoding="utf-8")
    item_filter = SimpleNamespace(item_type=[ItemType.Helm, ItemType.Sword])
    profile = SimpleNamespace(
        affixes=[SimpleNamespace(root={"equipment": item_filter})],
        aspect_upgrades=[],
        global_uniques=[],
        sigils=None,
        tributes=None,
        paragon=None,
    )
    store = SimpleNamespace(load=lambda _path: SimpleNamespace(profile=profile))
    monkeypatch.setattr(activity_log_widget.ProfileDocumentStore, "default", lambda: store)

    catalog = SimpleNamespace(
        grammar=SimpleNamespace(locale="zhCN"),
        item_types_dict={"Helm": "头盔", "Sword": "剑"},
        resolve_item_type=lambda value: value,
    )
    monkeypatch.setattr(catalog_display, "Dataloader", lambda: catalog)
    monkeypatch.setattr(
        catalog_display, "IniConfigLoader", lambda: SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    )

    summary = ActivityLogWidget._get_profile_summary(cast("ActivityLogWidget", object()), path)

    assert "剑" in summary
    assert "头盔" in summary
    assert "ItemType." not in summary
    assert item_filter.item_type == [ItemType.Helm, ItemType.Sword]
