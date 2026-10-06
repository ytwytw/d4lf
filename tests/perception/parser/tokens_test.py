from src.perception.parser.tokens import _AFFIX_RE


def test_affix_pattern_preserves_decimal_roll_with_integer_range() -> None:
    match = _AFFIX_RE.search("10.5 Attack Speed [8 - 12]")

    assert match is not None
    assert (match["affixvalue1"], match["minvalue1"], match["maxvalue1"]) == ("10.5", "8", "12")
