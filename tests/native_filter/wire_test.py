import pytest

from src.native_filter import NativeFilterError
from src.native_filter.wire import blob, fixed, integer, parse_fields


def test_wire_widths_and_field_boundaries_do_not_consume_next_field():
    fields = parse_fields(integer(1, 850) + fixed(2, 4294967295) + blob(3, b"abc"))
    assert [(entry.number, entry.wire, entry.value) for entry in fields] == [
        (1, 0, 850),
        (2, 5, 4294967295),
        (3, 2, b"abc"),
    ]


def test_overflow_and_truncation_are_rejected():
    for payload in (b"\x08" + b"\xff" * 10, b"\x15\x01\x02", b"\x1a\x04abc"):
        with pytest.raises(NativeFilterError):
            parse_fields(payload)
