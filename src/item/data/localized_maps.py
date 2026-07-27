"""Loading helpers for canonical-keyed localized string maps."""

import json
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    import pathlib


def _is_string_map(value: object) -> TypeGuard[dict[str, str]]:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


def _is_string_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_nested_string_map(value: object) -> TypeGuard[dict[str, dict[str, str]]]:
    return isinstance(value, dict) and all(
        isinstance(section, str) and _is_string_map(entries) for section, entries in value.items()
    )


def _is_metadata_map(value: object) -> TypeGuard[dict[str, dict[str, object]]]:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(metadata, dict) and all(isinstance(field, str) for field in metadata)
        for key, metadata in value.items()
    )


def _read_json(path: pathlib.Path) -> object:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_string_map(path: pathlib.Path) -> dict[str, str]:
    data = _read_json(path)
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
    return {**english, **_nonempty_strings(selected)}


def load_localized_display_map(language_dir: pathlib.Path, file_name: str) -> dict[str, str]:
    selected = _load_display_map(language_dir / file_name)
    if language_dir.name == "enUS":
        return selected
    english = _load_display_map(language_dir.parent / "enUS" / file_name)
    return {**english, **_nonempty_strings(selected)}


def load_localized_nested_string_map(language_dir: pathlib.Path, file_name: str) -> dict[str, dict[str, str]]:
    selected = _load_nested_string_map(language_dir / file_name)
    if language_dir.name == "enUS":
        return selected
    english = _load_nested_string_map(language_dir.parent / "enUS" / file_name)
    merged = {section: dict(entries) for section, entries in english.items()}
    for section, entries in selected.items():
        merged[section] = {**merged.get(section, {}), **_nonempty_strings(entries)}
    return merged


def load_localized_metadata_map(language_dir: pathlib.Path, file_name: str) -> dict[str, dict[str, object]]:
    selected = _load_metadata_map(language_dir / file_name)
    if language_dir.name == "enUS":
        return selected
    english = _load_metadata_map(language_dir.parent / "enUS" / file_name)
    merged = {canonical: dict(metadata) for canonical, metadata in english.items()}
    for canonical, metadata in selected.items():
        localized = {field: value for field, value in metadata.items() if not isinstance(value, str) or value.strip()}
        merged[canonical] = {**merged.get(canonical, {}), **localized}
    return merged


def _load_display_map(path: pathlib.Path) -> dict[str, str]:
    data = _read_json(path)
    if _is_string_list(data):
        return {value: value.replace("_", " ") for value in data}
    if _is_string_map(data):
        return data
    msg = f"Expected a JSON string list or string map: {path}"
    raise ValueError(msg)


def _load_nested_string_map(path: pathlib.Path) -> dict[str, dict[str, str]]:
    data = _read_json(path)
    if not _is_nested_string_map(data):
        msg = f"Expected a nested JSON string map: {path}"
        raise ValueError(msg)
    return data


def _load_metadata_map(path: pathlib.Path) -> dict[str, dict[str, object]]:
    data = _read_json(path)
    if not _is_metadata_map(data):
        msg = f"Expected a JSON metadata map: {path}"
        raise ValueError(msg)
    return data


def _nonempty_strings(values: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in values.items() if value.strip()}


__all__ = [
    "load_localized_display_map",
    "load_localized_metadata_map",
    "load_localized_nested_string_map",
    "load_localized_string_map",
    "load_string_map",
]
