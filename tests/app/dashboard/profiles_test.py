# ruff:file-ignore[invalid-function-name]
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from PyQt6.QtWidgets import QApplication, QLineEdit, QMenu, QPushButton, QVBoxLayout

from src.app.dashboard.drag import ActivityProfileDragMixin
from src.app.dashboard.profiles import ActivityProfileRowsMixin

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QLabel

    from src.app.dashboard.core import ActivityLogWidget


class _VisibilityFake:
    def __init__(self) -> None:
        self.visible = False

    def isVisible(self) -> bool:
        return self.visible

    def setVisible(self, visible: bool) -> None:
        self.visible = visible


class _ButtonFake:
    def __init__(self) -> None:
        self.label = "▶"

    def setText(self, label: str) -> None:
        self.label = label


def test_toggle_row_updates_visibility_and_button_label() -> None:
    mixin = cast("ActivityLogWidget", ActivityProfileRowsMixin())
    label = _VisibilityFake()
    button = _ButtonFake()

    ActivityProfileRowsMixin._toggle_row(mixin, cast("QLabel", label), cast("QPushButton", button))

    assert label.isVisible()
    assert button.label == "▼"

    ActivityProfileRowsMixin._toggle_row(mixin, cast("QLabel", label), cast("QPushButton", button))

    assert not label.isVisible()
    assert button.label == "▶"


def test_filter_profiles_matches_case_insensitively() -> None:
    mixin = cast("ActivityLogWidget", ActivityProfileDragMixin())
    matching = _VisibilityFake()
    other = _VisibilityFake()
    mixin.__dict__["_rows"] = {"Alpha": matching, "Beta": other}
    mixin.__dict__["_update_zebra_striping"] = lambda: None

    mixin._filter_profiles("ALP")

    assert matching.isVisible()
    assert not other.isVisible()


def test_profile_tool_actions_trigger_with_their_own_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _app = QApplication.instance() or QApplication([])
    directory = tmp_path / "profiles"
    directory.mkdir()
    for name in ("Alpha", "Beta"):
        (directory / f"{name}.yaml").write_text("Affixes: []", encoding="utf-8")
    calls: list[tuple[str, str]] = []
    window = SimpleNamespace(
        open_native_filter=lambda name: calls.append(("filter", name)),
        open_equipment_knowledge=lambda name: calls.append(("knowledge", name)),
    )
    dashboard = cast(
        "ActivityLogWidget",
        SimpleNamespace(
            profile_layout=QVBoxLayout(),
            _config=SimpleNamespace(user_dir=tmp_path, general=SimpleNamespace(profiles=[])),
            _main_window=window,
            _checkboxes={},
            _rows={},
            profile_search_input=QLineEdit(),
            _create_row_btn=lambda text: QPushButton(text),
            _start_drag=lambda *_args: None,
            _on_toggle=lambda *_args: None,
            _get_profile_summary=lambda _path: "",
            _update_zebra_striping=lambda: None,
        ),
    )
    ActivityProfileRowsMixin.refresh_profiles(dashboard)
    for name in ("Alpha", "Beta"):
        menus = dashboard._rows[name].findChildren(QMenu)
        assert len(menus) == 1
        actions = menus[0].actions()
        assert [action.text() for action in actions] == ["生成游戏过滤器", "装备来源与词条"]
        for action in actions:
            action.trigger()
    assert calls == [("filter", "Alpha"), ("knowledge", "Alpha"), ("filter", "Beta"), ("knowledge", "Beta")]
