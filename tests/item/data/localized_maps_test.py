import json

import pytest

from src.item.data.localized_maps import load_localized_string_map, load_string_map


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
    (chinese / "values.json").write_text(json.dumps({"first": "一"}), encoding="utf-8")

    assert load_localized_string_map(chinese, "values.json") == {"first": "一", "second": "two"}
