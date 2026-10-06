import base64
from copy import deepcopy
from pathlib import Path

import pytest

from src.native_filter import (
    Action,
    Condition,
    ConditionKind,
    NativeFilter,
    NativeFilterError,
    Rule,
    decode_filter,
    encode_filter,
)
from src.native_filter.wire import byte_values, parse_fields


def test_website_sample_roundtrips_with_actual_game_power_semantics():
    code = (Path(__file__).parent / "fixtures" / "seven-rules.txt").read_text(encoding="utf-8").strip()
    document = decode_filter(code)
    assert not document.opaque
    assert document.name == "幻影尖啸850+·紫装法典全保留"
    assert len(document.rules) == 7
    # InfinityBuilds reversed these fields: its "850+" sample actually sets a maximum.
    assert document.rules[3].conditions[0].minimum is None
    assert document.rules[3].conditions[0].maximum == 850
    assert document.rules[4].conditions[-1].min_count == 2
    assert document.rules[5].action == Action.HIDE_ALL
    assert encode_filter(document) == code
    document.original_payload = b""
    assert encode_filter(document) == code


def test_game_export_keeps_observed_power_bounds_and_roundtrips():
    code = (Path(__file__).parent / "fixtures" / "game-73764-power-123-456.txt").read_text(encoding="utf-8").strip()
    document = decode_filter(code)
    assert not document.opaque
    assert document.name == "战利品筛选 #3"
    assert len(document.rules) == 13
    powers = {
        rule.name: (condition.minimum, condition.maximum)
        for rule in document.rules
        for condition in rule.conditions
        if condition.kind == ConditionKind.ITEM_POWER
    }
    assert powers == {
        "Amulet": (None, 100),
        "Boots": (None, 100),
        "ChestArmor": (123, 456),
        "Gloves": (None, 100),
        "Helm": (None, 100),
        "Legs": (None, 100),
        "Ring": (None, 100),
        "Ring2": (None, 100),
        "Staff(x2)": (None, 100),
    }
    assert encode_filter(document) == code
    document.original_payload = b""
    assert encode_filter(document) == code


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected"),
    [(123, None, "0800207b"), (None, 456, "080028c803"), (123, 456, "0800207b28c803")],
)
def test_power_bounds_use_game_fields_four_and_five(minimum, maximum, expected):
    condition = Condition(ConditionKind.ITEM_POWER, minimum=minimum, maximum=maximum)
    document = NativeFilter(rules=[Rule(conditions=[condition])])
    fields = parse_fields(base64.b64decode(encode_filter(document)))
    rule = parse_fields(byte_values(fields, 1)[0])
    assert byte_values(rule, 4) == (bytes.fromhex(expected),)


def test_all_ten_condition_types_and_unicode():
    conditions = [
        Condition(ConditionKind.ITEM_POWER, minimum=1, maximum=900),
        Condition(ConditionKind.RARITY, mask=48),
        Condition(ConditionKind.PROPERTIES, mask=4),
        Condition(ConditionKind.CODEX),
        Condition(ConditionKind.GREATER_AFFIX, min_count=2),
        Condition(ConditionKind.ITEM_TYPES, sno_ids=(446832,)),
        Condition(ConditionKind.REQUIRED_AFFIXES, sno_ids=(577173, 583654), min_count=1, ga_sno_ids=(583654,)),
        Condition(ConditionKind.OPTIONAL_AFFIXES, sno_ids=(577173,), min_count=1),
        Condition(ConditionKind.SPECIFIC_ITEMS, sno_ids=(186283,)),
        Condition(ConditionKind.TALISMAN_SET, set_sno_id=42, piece_sno_ids=(43, 44)),
    ]
    original = NativeFilter(
        "测试🎯",
        [Rule(f"规则 {index}", index % 4, "#123456", index != 2, [value]) for index, value in enumerate(conditions)],
    )
    decoded = decode_filter(encode_filter(original))
    assert not decoded.opaque
    assert decoded.name == original.name
    assert decoded.rules[0].color_hex == "#123456"
    assert not decoded.rules[2].enabled
    assert decoded.rules[6].conditions[0].ga_sno_ids == (583654,)
    assert decoded.rules[9].conditions[0].piece_sno_ids == (43, 44)
    assert encode_filter(decoded) == encode_filter(original)


def test_unknown_64bit_field_is_lossless_and_edit_protected():
    payload = base64.b64decode(encode_filter(NativeFilter())) + b"\x49\x01\x02\x03\x04\x05\x06\x07\x08"
    code = base64.b64encode(payload).decode()
    document = decode_filter(code)
    assert document.opaque
    assert encode_filter(document) == code
    document.name = "changed"
    with pytest.raises(NativeFilterError, match="未知字段"):
        encode_filter(document)


def test_unknown_condition_and_unrecognized_condition_parameter_are_locked():
    # Root rule -> unknown condition type 10; unknown varint parameter survives unchanged.
    for condition in (b"\x08\x0a\x50\x01", b"\x08\x03\x30\x00"):
        rule = b"\x22" + bytes([len(condition)]) + condition
        payload = b"\x0a" + bytes([len(rule)]) + rule + b"\x12\x01X"
        code = base64.b64encode(payload).decode()
        document = decode_filter(code)
        assert document.opaque
        assert encode_filter(document) == code


@pytest.mark.parametrize("code", ["", "not-base64", "CgU=", "AA==", "CA==", "CgE=", "!!!!"])
def test_malformed_input_fails_without_partial_document(code):
    with pytest.raises(NativeFilterError):
        decode_filter(code)


def test_rule_limit_and_order():
    document = NativeFilter(rules=[Rule(str(index)) for index in range(25)])
    assert len(decode_filter(encode_filter(document)).rules) == 25
    document.rules.append(Rule("26"))
    with pytest.raises(NativeFilterError, match="25"):
        encode_filter(document)
    document.rules.pop()
    original = encode_filter(document)
    document.rules.reverse()
    assert encode_filter(document) != original
    assert decode_filter(encode_filter(document)).rules[0].name == "24"


@pytest.mark.parametrize(
    "condition",
    [
        Condition(ConditionKind.ITEM_POWER, minimum=-1),
        Condition(ConditionKind.ITEM_POWER, minimum=900, maximum=800),
        Condition(ConditionKind.ITEM_TYPES, sno_ids=(2**32,)),
        Condition(ConditionKind.REQUIRED_AFFIXES, sno_ids=(1,), min_count=2),
        Condition(ConditionKind.REQUIRED_AFFIXES, sno_ids=(1,), ga_sno_ids=(2,)),
    ],
)
def test_invalid_values_do_not_wrap_or_silently_change(condition):
    document = NativeFilter(rules=[Rule(conditions=[condition])])
    with pytest.raises(NativeFilterError):
        encode_filter(document)


def test_known_import_remains_editable_without_changing_other_rules():
    source = NativeFilter(rules=[Rule("保留", conditions=[Condition(ConditionKind.RARITY, mask=32)]), Rule("其他")])
    edited = decode_filter(encode_filter(source))
    untouched = deepcopy(edited.rules[0])
    edited.rules[1].enabled = False
    decoded = decode_filter(encode_filter(edited))
    assert decoded.rules[0] == untouched
    assert not decoded.rules[1].enabled
