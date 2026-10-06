"""Native game export: base64 of protobuf wire bytes, without compression."""

import base64
import binascii
import hashlib
import json
import re
from dataclasses import asdict

from src.native_filter.models import (
    KINDS,
    MAX_RULES,
    Action,
    Condition,
    ConditionKind,
    NativeFilter,
    NativeFilterError,
    Rule,
)
from src.native_filter.wire import MAX_PAYLOAD, blob, fixed, integer, uint


def semantic_digest(document: NativeFilter) -> str:
    data = asdict(document)
    for key in ("original_payload", "original_digest", "opaque"):
        data.pop(key)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_condition(condition: Condition) -> None:
    kind = condition.kind
    if kind not in KINDS:
        msg = "未知条件只能原样导出，不能编辑"
        raise NativeFilterError(msg)
    for value in (*condition.sno_ids, *condition.ga_sno_ids, *condition.piece_sno_ids):
        uint(value)
        if value == 0:
            msg = "SNO ID 不能为 0"
            raise NativeFilterError(msg)
    for value in (condition.minimum, condition.maximum, condition.set_sno_id):
        if value is not None:
            uint(value)
    uint(condition.mask)
    uint(condition.min_count)
    if kind == ConditionKind.ITEM_POWER:
        if condition.minimum is None and condition.maximum is None:
            msg = "物品强度至少需要一个边界"
            raise NativeFilterError(msg)
        if condition.minimum is not None and condition.maximum is not None and condition.minimum > condition.maximum:
            msg = "最低物品强度不能大于最高物品强度"
            raise NativeFilterError(msg)
    if kind in {ConditionKind.RARITY, ConditionKind.PROPERTIES} and condition.mask == 0:
        msg = "至少选择一个稀有度或物品属性"
        raise NativeFilterError(msg)
    if kind in {ConditionKind.RARITY, ConditionKind.PROPERTIES}:
        known = 127 if kind == ConditionKind.RARITY else 37
        if condition.mask & ~known:
            msg = "未知的稀有度或物品属性标记只能原样导出"
            raise NativeFilterError(msg)
    if kind in {ConditionKind.ITEM_TYPES, ConditionKind.SPECIFIC_ITEMS} and not condition.sno_ids:
        msg = "此条件至少需要一个 SNO ID"
        raise NativeFilterError(msg)
    if kind in {ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
        if not 1 <= condition.min_count <= len(set(condition.sno_ids)):
            msg = "所需词缀数必须在 1 与所选不同词缀数之间"
            raise NativeFilterError(msg)
        if not set(condition.ga_sno_ids) <= set(condition.sno_ids):
            msg = "大词缀必须属于已选择的词缀"
            raise NativeFilterError(msg)
    if kind == ConditionKind.TALISMAN_SET and not condition.set_sno_id:
        msg = "套装条件需要套装 SNO ID"
        raise NativeFilterError(msg)


def validate_document(document: NativeFilter) -> None:
    if not 1 <= len(document.rules) <= MAX_RULES:
        msg = f"游戏过滤器必须包含 1–{MAX_RULES} 条规则"
        raise NativeFilterError(msg)
    if not document.name.strip():
        msg = "请填写过滤器名称"
        raise NativeFilterError(msg)
    for rule in document.rules:
        if rule.action not in set(Action):
            msg = "未知动作只能原样导出"
            raise NativeFilterError(msg)
        if re.fullmatch(r"#[0-9a-fA-F]{6}", rule.color_hex) is None:
            msg = "颜色必须为 #RRGGBB"
            raise NativeFilterError(msg)
        kinds = [condition.kind for condition in rule.conditions]
        if len(kinds) != len(set(kinds)):
            msg = "同一规则不能重复使用相同条件类型"
            raise NativeFilterError(msg)
        for condition in rule.conditions:
            validate_condition(condition)


def _encode_condition(condition: Condition) -> bytes:
    kind = condition.kind
    result = integer(1, KINDS.index(kind))
    if kind == ConditionKind.ITEM_POWER:
        if condition.minimum is not None:
            result += integer(4, condition.minimum)
        if condition.maximum is not None:
            result += integer(5, condition.maximum)
    elif kind in {ConditionKind.RARITY, ConditionKind.PROPERTIES}:
        result += integer(4, condition.mask)
    elif kind == ConditionKind.CODEX:
        result += integer(6, 1)
    elif kind == ConditionKind.GREATER_AFFIX:
        result += integer(4, condition.min_count) + integer(6, 1)
    elif kind in {ConditionKind.ITEM_TYPES, ConditionKind.SPECIFIC_ITEMS}:
        result += b"".join(fixed(2, sno_id) for sno_id in condition.sno_ids)
    elif kind in {ConditionKind.REQUIRED_AFFIXES, ConditionKind.OPTIONAL_AFFIXES}:
        result += b"".join(fixed(2, sno_id) for sno_id in condition.sno_ids)
        result += b"".join(blob(3, fixed(1, sno_id) + fixed(2, sno_id)) for sno_id in condition.ga_sno_ids)
        result += integer(4, condition.min_count)
    elif kind == ConditionKind.TALISMAN_SET and condition.set_sno_id is not None:
        result += fixed(2, condition.set_sno_id)
        if condition.piece_sno_ids:
            params = fixed(1, condition.set_sno_id)
            params += b"".join(fixed(2, sno_id) for sno_id in condition.piece_sno_ids)
            result += blob(3, params)
    return result


def _encode_rule(rule: Rule) -> bytes:
    color = bytes.fromhex(rule.color_hex[1:]) + b"\xff"
    result = blob(1, rule.name.encode("utf-8")) + integer(2, int(rule.action))
    result += fixed(3, int.from_bytes(color, "little"))
    result += b"".join(blob(4, _encode_condition(condition)) for condition in rule.conditions)
    return result + integer(5, int(rule.enabled))


def encode_filter(document: NativeFilter) -> str:
    """Re-export untouched imports exactly; refuse destructive opaque edits."""
    digest = semantic_digest(document)
    if document.original_payload and digest == document.original_digest:
        return base64.b64encode(document.original_payload).decode("ascii")
    if document.opaque:
        msg = "此导入包含未知字段；为保留原意，只能原样导出。请新建独立过滤器进行编辑。"
        raise NativeFilterError(msg)
    validate_document(document)
    payload = b"".join(blob(1, _encode_rule(rule)) for rule in document.rules)
    payload += blob(2, document.name.encode("utf-8"))
    if document.raw_f3 is not None:
        payload += integer(3, document.raw_f3)
    if document.raw_f4 is not None:
        payload += integer(4, document.raw_f4)
    if len(payload) > MAX_PAYLOAD:
        msg = "过滤器超过本地导出上限 1 MiB"
        raise NativeFilterError(msg)
    return base64.b64encode(payload).decode("ascii")


def decode_payload(code: str) -> bytes:
    code = code.strip()
    if not code or len(code) > MAX_PAYLOAD * 2:
        msg = "过滤器代码为空或过长"
        raise NativeFilterError(msg)
    try:
        payload = base64.b64decode(code, validate=True)
    except (binascii.Error, ValueError) as error:
        msg = "过滤器代码不是有效的 Base64"
        raise NativeFilterError(msg) from error
    if len(payload) > MAX_PAYLOAD:
        msg = "过滤器超过本地读取上限 1 MiB"
        raise NativeFilterError(msg)
    return payload
