import json
from pathlib import Path
from string import Formatter

from src.localization import catalog, translate

CATALOG_ROOT = Path(__file__).parents[2] / "assets" / "lang"


def _catalog(locale: str) -> dict[str, str]:
    with (CATALOG_ROOT / locale / "ui.json").open(encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


def _placeholders(template: str) -> set[str]:
    return {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}


def test_catalogs_have_matching_keys_and_placeholders() -> None:
    english = _catalog("enUS")
    chinese = _catalog("zhCN")

    assert chinese.keys() == english.keys()
    assert {key: _placeholders(value) for key, value in chinese.items()} == {
        key: _placeholders(value) for key, value in english.items()
    }


def test_translate_uses_requested_locale_and_formats_values() -> None:
    assert translate("app.title", locale="zhCN", version="10.0.0") == ("D4LF - 暗黑破坏神 IV 装备过滤器 v10.0.0")


def test_translate_falls_back_to_english_then_default() -> None:
    assert translate("tabs.dashboard", locale="missing") == "Dashboard"
    assert translate("missing.message", "Fallback", locale="zhCN") == "Fallback"


def test_translate_treats_empty_localized_text_as_missing(monkeypatch) -> None:
    catalogs = {"zhCN": {"message": "  "}, "enUS": {"message": "English"}}
    monkeypatch.setattr(catalog, "_load_catalog", lambda locale: catalogs.get(locale, {}))

    assert catalog.translate("message", locale="zhCN") == "English"
