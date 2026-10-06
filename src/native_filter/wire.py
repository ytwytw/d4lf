"""Small bounded protobuf wire reader; no generated/copied third-party code."""

from dataclasses import dataclass

from src.native_filter.models import NativeFilterError

MAX_PAYLOAD = 1_048_576


@dataclass(frozen=True)
class WireField:
    number: int
    wire: int
    value: int | bytes


def uint(value: int, bits: int = 32) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << bits):
        msg = f"数值必须是 {bits} 位非负整数: {value!r}"
        raise NativeFilterError(msg)
    return value


def varint(value: int) -> bytes:
    uint(value, 64)
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _read_varint(payload: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for index in range(10):
        if offset >= len(payload):
            msg = "过滤器包含不完整的整数"
            raise NativeFilterError(msg)
        byte = payload[offset]
        offset += 1
        value |= (byte & 127) << (7 * index)
        if byte < 128:
            if value >= 1 << 64:
                msg = "过滤器整数超出范围"
                raise NativeFilterError(msg)
            return value, offset
    msg = "过滤器整数过长"
    raise NativeFilterError(msg)


def parse_fields(payload: bytes) -> tuple[WireField, ...]:
    if len(payload) > MAX_PAYLOAD:
        msg = "过滤器超过本地安全读取上限 1 MiB"
        raise NativeFilterError(msg)
    fields = []
    offset = 0
    while offset < len(payload):
        tag, offset = _read_varint(payload, offset)
        number, wire = tag >> 3, tag & 7
        if not 1 <= number < 1 << 29:
            msg = "过滤器字段编号无效"
            raise NativeFilterError(msg)
        if wire == 0:
            value, offset = _read_varint(payload, offset)
        elif wire in {1, 2, 5}:
            if wire == 2:
                length, offset = _read_varint(payload, offset)
            else:
                length = 8 if wire == 1 else 4
            end = offset + length
            if end > len(payload):
                msg = "过滤器包含截断的数据字段"
                raise NativeFilterError(msg)
            part = payload[offset:end]
            value = part if wire == 2 else int.from_bytes(part, "little")
            offset = end
        else:
            msg = f"暂不支持的 protobuf wire 类型: {wire}"
            raise NativeFilterError(msg)
        fields.append(WireField(number, wire, value))
    return tuple(fields)


def integer(number: int, value: int) -> bytes:
    return varint(number << 3) + varint(uint(value))


def fixed(number: int, value: int) -> bytes:
    return varint((number << 3) | 5) + uint(value).to_bytes(4, "little")


def blob(number: int, value: bytes) -> bytes:
    return varint((number << 3) | 2) + varint(len(value)) + value


def numbers(fields: tuple[WireField, ...], number: int, wire: int = 0) -> tuple[int, ...]:
    return tuple(
        field.value
        for field in fields
        if field.number == number and field.wire == wire and isinstance(field.value, int)
    )


def byte_values(fields: tuple[WireField, ...], number: int) -> tuple[bytes, ...]:
    return tuple(
        field.value for field in fields if field.number == number and field.wire == 2 and isinstance(field.value, bytes)
    )


def last_number(fields: tuple[WireField, ...], number: int, default: int = 0, wire: int = 0) -> int:
    values = numbers(fields, number, wire)
    return values[-1] if values else default


def text_value(fields: tuple[WireField, ...], number: int, default: str = "") -> str:
    values = byte_values(fields, number)
    try:
        return values[-1].decode("utf-8") if values else default
    except UnicodeDecodeError as error:
        msg = "过滤器名称不是有效的 UTF-8"
        raise NativeFilterError(msg) from error


def has_unknown(fields: tuple[WireField, ...], allowed: set[tuple[int, int]]) -> bool:
    return any((field.number, field.wire) not in allowed for field in fields)
