import json

from src.tools.data_generation.common import get_power_id, string_list_map, write_json_file


def test_string_list_map_converts_localized_entries(tmp_path) -> None:
    path = tmp_path / "strings.json"
    path.write_text(json.dumps({"arStrings": [{"szLabel": "one", "szText": "One"}]}), encoding="utf-8")

    assert string_list_map(path) == {"one": "One"}


def test_get_power_id_extracts_file_stem() -> None:
    assert get_power_id({42: "powers/example.json"}, 42) == "example"


def test_write_json_file_has_stable_utf8_lf_sorted_bytes(tmp_path) -> None:
    path = tmp_path / "generated.json"
    data = {"z": ["次级和谐贡品"], "a": 1}

    write_json_file(path, data)

    expected = '{\n    "a": 1,\n    "z": [\n        "次级和谐贡品"\n    ]\n}\n'.encode()
    assert path.read_bytes() == expected
    assert json.loads(path.read_bytes()) == data
    write_json_file(path, data)
    assert path.read_bytes() == expected
