"""Decode known fields and retain the full payload for lossless re-export."""

from src.native_filter.codec import decode_payload, semantic_digest, validate_document
from src.native_filter.models import KINDS, Condition, ConditionKind, NativeFilter, NativeFilterError, Rule
from src.native_filter.wire import byte_values, has_unknown, last_number, numbers, parse_fields, text_value


def _decode_condition(payload: bytes) -> tuple[Condition, bool]:
    fields = parse_fields(payload)
    type_number = last_number(fields, 1)
    kind = KINDS[type_number] if type_number < len(KINDS) else ConditionKind.UNKNOWN
    ids = numbers(fields, 2, 5)
    ga_ids: list[int] = []
    piece_ids: list[int] = []
    set_id = None
    opaque = has_unknown(fields, {(1, 0), (2, 5), (3, 2), (4, 0), (5, 0), (6, 0)})
    for child in byte_values(fields, 3):
        params = parse_fields(child)
        opaque |= has_unknown(params, {(1, 5), (2, 5)})
        first = numbers(params, 1, 5)
        second = numbers(params, 2, 5)
        if kind in {ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
            opaque |= len(first) != 1 or first != second
            ga_ids.extend(first)
        elif kind == ConditionKind.TALISMAN_SET:
            set_id = first[-1] if first else set_id
            piece_ids.extend(second)
        else:
            opaque = True
    condition = Condition(
        kind=kind,
        sno_ids=ids,
        ga_sno_ids=tuple(ga_ids),
        piece_sno_ids=tuple(piece_ids),
        set_sno_id=set_id if set_id is not None else ids[0] if ids and kind == ConditionKind.TALISMAN_SET else None,
        unknown_type=type_number if kind == ConditionKind.UNKNOWN else None,
    )
    values4, values5 = numbers(fields, 4), numbers(fields, 5)
    if kind == ConditionKind.ITEM_POWER:
        condition.minimum = values4[-1] if values4 else None
        condition.maximum = values5[-1] if values5 else None
    elif kind in {ConditionKind.RARITY, ConditionKind.PROPERTIES}:
        condition.mask = last_number(fields, 4)
    elif kind in {ConditionKind.GREATER_AFFIX, ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
        condition.min_count = last_number(fields, 4, len(ids) if ids else 0)
    allowed = {
        ConditionKind.ITEM_POWER: {1, 4, 5},
        ConditionKind.RARITY: {1, 4},
        ConditionKind.PROPERTIES: {1, 4},
        ConditionKind.CODEX: {1, 6},
        ConditionKind.GREATER_AFFIX: {1, 4, 6},
        ConditionKind.ITEM_TYPES: {1, 2},
        ConditionKind.SPECIFIC_ITEMS: {1, 2},
        ConditionKind.REQUIRED_AFFIXES: {1, 2, 3, 4},
        ConditionKind.OPTIONAL_AFFIXES: {1, 2, 3, 4},
        ConditionKind.TALISMAN_SET: {1, 2, 3},
    }.get(kind, set())
    opaque |= any(field.number not in allowed for field in fields)
    opaque |= any(len(numbers(fields, number)) > 1 for number in (1, 4, 5, 6))
    if kind in {ConditionKind.CODEX, ConditionKind.GREATER_AFFIX}:
        opaque |= last_number(fields, 6, 1) != 1
    return condition, opaque


def _decode_rule(payload: bytes) -> tuple[Rule, bool]:
    fields = parse_fields(payload)
    color = last_number(fields, 3, 0xFFFF0000, 5)
    color_hex = "#" + color.to_bytes(4, "little")[:3].hex()
    rule = Rule(text_value(fields, 1), last_number(fields, 2), color_hex, last_number(fields, 5, 1) != 0)
    opaque = has_unknown(fields, {(1, 2), (2, 0), (3, 5), (4, 2), (5, 0)})
    opaque |= color >> 24 != 255 or last_number(fields, 5, 1) not in {0, 1}
    opaque |= len(byte_values(fields, 1)) > 1 or any(len(numbers(fields, number)) > 1 for number in (2, 5))
    opaque |= len(numbers(fields, 3, 5)) > 1
    for value in byte_values(fields, 4):
        condition, unknown = _decode_condition(value)
        opaque |= unknown
        rule.conditions.append(condition)
    return rule, opaque


def decode_filter(code: str) -> NativeFilter:
    payload = decode_payload(code)
    fields = parse_fields(payload)
    document = NativeFilter(name=text_value(fields, 2), rules=[], original_payload=payload)
    document.raw_f3 = last_number(fields, 3) if numbers(fields, 3) else None
    document.raw_f4 = last_number(fields, 4) if numbers(fields, 4) else None
    document.opaque = has_unknown(fields, {(1, 2), (2, 2), (3, 0), (4, 0)})
    document.opaque |= len(byte_values(fields, 2)) > 1 or any(len(numbers(fields, number)) > 1 for number in (3, 4))
    for value in byte_values(fields, 1):
        rule, unknown = _decode_rule(value)
        document.opaque |= unknown
        document.rules.append(rule)
    if not document.rules:
        msg = "代码中没有过滤器规则"
        raise NativeFilterError(msg)
    try:
        validate_document(document)
    except NativeFilterError:
        document.opaque = True
    document.original_digest = semantic_digest(document)
    return document
