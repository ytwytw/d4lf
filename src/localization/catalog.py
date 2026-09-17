"""Stable-ID message catalog for application-owned interface text."""

import json
import logging
from functools import cache
from typing import cast

from src.settings import BASE_DIR, get_settings

LOGGER = logging.getLogger(__name__)
DEFAULT_LOCALE = "enUS"


@cache
def _load_catalog(locale: str) -> dict[str, str]:
    catalog_path = BASE_DIR / "assets" / "lang" / locale / "ui.json"
    try:
        with catalog_path.open(encoding="utf-8") as catalog_file:
            data = json.load(catalog_file)
    except OSError, json.JSONDecodeError:
        LOGGER.exception("Could not load UI translations from %s", catalog_path)
        return {}
    if not isinstance(data, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in data.items()
    ):
        LOGGER.error("UI translation catalog must contain only string keys and values: %s", catalog_path)
        return {}
    return cast("dict[str, str]", data)


def translate(message_id: str, default: str | None = None, *, locale: str | None = None, **values: object) -> str:
    """Translate a stable message ID with English and caller-provided fallbacks."""
    selected_locale = locale or str(get_settings().general.language)
    template = _load_catalog(selected_locale).get(message_id)
    if not template or not template.strip():
        template = _load_catalog(DEFAULT_LOCALE).get(message_id)
    if not template or not template.strip():
        template = default or message_id
    try:
        return template.format(**values)
    except KeyError, ValueError:
        LOGGER.exception("Could not format UI message %s for locale %s", message_id, selected_locale)
        fallback = _load_catalog(DEFAULT_LOCALE).get(message_id)
        if not fallback or not fallback.strip():
            fallback = default or message_id
        try:
            return fallback.format(**values)
        except KeyError, ValueError:
            return fallback
