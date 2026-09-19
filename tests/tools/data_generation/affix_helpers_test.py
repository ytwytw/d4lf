from src.tools.data_generation.affix_helpers import power_index, replace_numeric_value_placeholders


def test_replace_numeric_value_placeholders_removes_formatting_tokens() -> None:
    description = "+{VALUE1} {c_number}{VALUE2}%"

    assert replace_numeric_value_placeholders(description) == "+# #%"


def test_power_index_uses_core_toc_before_file_fallback(tmp_path) -> None:
    assert power_index({"29": {"42": "Power_example"}}, tmp_path) == {42: "Power_example"}


def test_power_index_preserves_legacy_file_fallback(tmp_path) -> None:
    power_dir = tmp_path / "json/base/meta/Power"
    power_dir.mkdir(parents=True)
    (power_dir / "example.json").write_text('{"__snoID__": 42, "__fileName__": "Power_example"}', encoding="utf-8")

    assert power_index({}, tmp_path) == {42: "Power_example"}
