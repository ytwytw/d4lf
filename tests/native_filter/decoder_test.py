import base64

from src.native_filter import decode_filter, encode_filter


def test_nondefault_alpha_is_preserved_and_locked():
    # One named rule with a translucent color, which the editor cannot represent.
    payload = b"\x0a\x0a\x0a\x03abc\x1d\x12\x34\x56\x78\x12\x01X"
    code = base64.b64encode(payload).decode()
    document = decode_filter(code)
    assert document.rules[0].color_hex == "#123456"
    assert document.opaque
    assert encode_filter(document) == code


def test_power_bounds_decode_independent_wire_sample():
    # ItemPowerRange: field 4 is minimum, field 5 is maximum (game build 3.2.2.73764).
    payload = bytes.fromhex("0a0922070800207b28c803120158")
    document = decode_filter(base64.b64encode(payload).decode())
    assert not document.opaque
    condition = document.rules[0].conditions[0]
    assert condition.minimum == 123
    assert condition.maximum == 456
