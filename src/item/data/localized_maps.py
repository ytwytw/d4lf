"""Loading helpers for canonical-keyed localized string maps."""

import json
import pathlib
from typing import TypeGuard


def _is_string_map(value: object) -> TypeGuard[dict[str, str]]:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


def load_string_map(path: pathlib.Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as source:
        data: object = json.load(source)
    if not _is_string_map(data):
        msg = f"Expected a JSON object containing only string keys and values: {path}"
        raise ValueError(msg)
    return data


def load_localized_string_map(language_dir: pathlib.Path, file_name: str) -> dict[str, str]:
    """Load localized text while preserving every canonical English key."""
    selected = load_string_map(language_dir / file_name)
    if language_dir.name == "enUS":
        return selected
    english = load_string_map(language_dir.parent / "enUS" / file_name)
    return {**english, **selected}


__all__ = ["load_localized_string_map", "load_string_map"]
