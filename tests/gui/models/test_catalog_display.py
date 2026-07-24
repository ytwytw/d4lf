from types import SimpleNamespace

from src.gui.models import catalog_display
from src.item.data.item_type import ItemType


class _Catalog:
    def __init__(self, locale: str = "zhCN") -> None:
        self.grammar = SimpleNamespace(locale=locale)
        self.item_types_dict = {"Helm": "头盔"}
        self.aspect_dict = {"accelerating": "加速"}
        self.aspect_unique_dict = {"test_unique": {"display_name": "测试暗金"}}
        self.set_dict = {"test_set": "测试套装"}
        self.load_calls = 0

    def load_data(self) -> None:
        self.load_calls += 1
        self.grammar.locale = "zhCN"

    def resolve_item_type(self, value: str) -> str | None:
        return "Helm" if value in {"Helm", "helm", "头盔"} else None

    def resolve_aspect(self, value: str) -> str | None:
        return "accelerating" if value in {"accelerating", "加速"} else None

    def resolve_unique(self, value: str) -> str | None:
        return "test_unique" if value in {"test_unique", "测试暗金"} else None


def _install_catalog(monkeypatch, catalog: _Catalog) -> None:
    monkeypatch.setattr(catalog_display, "Dataloader", lambda: catalog)
    monkeypatch.setattr(
        catalog_display, "IniConfigLoader", lambda: SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    )


def test_catalog_display_uses_localized_names_without_changing_canonical_ids(monkeypatch) -> None:
    catalog = _Catalog()
    _install_catalog(monkeypatch, catalog)

    assert catalog_display.item_type_display_name(ItemType.Helm) == "头盔"
    assert catalog_display.aspect_display_name("accelerating") == "加速"
    assert catalog_display.unique_display_name("test_unique") == "测试暗金"
    assert catalog_display.set_display_name("test_set") == "测试套装"
    assert catalog_display.resolve_aspect_canonical("加速") == "accelerating"
    assert catalog_display.resolve_unique_canonical("测试暗金") == "test_unique"
    assert catalog_display.catalog_group_label("Weapons") == "武器"
    assert catalog_display.catalog_group_label("Non-weapons") == "非武器"


def test_catalog_display_reloads_when_configured_locale_changes(monkeypatch) -> None:
    catalog = _Catalog(locale="enUS")
    _install_catalog(monkeypatch, catalog)

    assert catalog_display.aspect_display_name("accelerating") == "加速"
    assert catalog.load_calls == 1
