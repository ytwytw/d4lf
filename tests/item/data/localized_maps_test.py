import json

import pytest

from src.item.data.localized_maps import (
    load_localized_display_map,
    load_localized_metadata_map,
    load_localized_nested_string_map,
    load_localized_string_map,
    load_string_map,
)


def test_load_string_map_returns_string_values(tmp_path) -> None:
    path = tmp_path / "strings.json"
    path.write_text(json.dumps({"first": "one", "second": "two"}), encoding="utf-8")

    assert load_string_map(path) == {"first": "one", "second": "two"}


@pytest.mark.parametrize("payload", [[], {"first": 1}, {"first": None}])
def test_load_string_map_rejects_non_string_maps(tmp_path, payload) -> None:
    path = tmp_path / "strings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="only string keys and values"):
        load_string_map(path)


def test_load_localized_string_map_preserves_english_keys(tmp_path) -> None:
    english = tmp_path / "enUS"
    chinese = tmp_path / "zhCN"
    english.mkdir()
    chinese.mkdir()
    (english / "values.json").write_text(json.dumps({"first": "one", "second": "two"}), encoding="utf-8")
    (chinese / "values.json").write_text(json.dumps({"first": "一", "second": ""}), encoding="utf-8")

    assert load_localized_string_map(chinese, "values.json") == {"first": "一", "second": "two"}


def test_load_localized_display_map_merges_english_lists_with_localized_maps(tmp_path) -> None:
    english = tmp_path / "enUS"
    chinese = tmp_path / "zhCN"
    english.mkdir()
    chinese.mkdir()
    (english / "values.json").write_text(json.dumps(["first_value", "second_value"]), encoding="utf-8")
    (chinese / "values.json").write_text(json.dumps({"first_value": "第一", "second_value": ""}), encoding="utf-8")

    assert load_localized_display_map(chinese, "values.json") == {"first_value": "第一", "second_value": "second value"}


def test_load_localized_nested_string_map_preserves_sections_and_nonempty_fallbacks(tmp_path) -> None:
    english = tmp_path / "enUS"
    chinese = tmp_path / "zhCN"
    english.mkdir()
    chinese.mkdir()
    (english / "values.json").write_text(
        json.dumps({"first": {"one": "one", "two": "two"}, "second": {"three": "three"}}), encoding="utf-8"
    )
    (chinese / "values.json").write_text(json.dumps({"first": {"one": "一", "two": ""}}), encoding="utf-8")

    assert load_localized_nested_string_map(chinese, "values.json") == {
        "first": {"one": "一", "two": "two"},
        "second": {"three": "three"},
    }


def test_load_localized_metadata_map_preserves_records_and_ignores_empty_text(tmp_path) -> None:
    english = tmp_path / "enUS"
    chinese = tmp_path / "zhCN"
    english.mkdir()
    chinese.mkdir()
    (english / "values.json").write_text(
        json.dumps({"first": {"display_name": "First", "num_inherents": 1}, "second": {"num_inherents": 0}}),
        encoding="utf-8",
    )
    (chinese / "values.json").write_text(
        json.dumps({"first": {"display_name": "", "num_inherents": 2}}), encoding="utf-8"
    )

    assert load_localized_metadata_map(chinese, "values.json") == {
        "first": {"display_name": "First", "num_inherents": 2},
        "second": {"num_inherents": 0},
    }
