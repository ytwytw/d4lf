"""Read public D2Core planner payloads through its browser-facing endpoint."""

import json
from typing import cast

import httpx

CLOUDBASE_ENDPOINT = "https://tcb-api.tencentcloudapi.com/web"
CLOUDBASE_ENV = "diablocore-4gkv4qjs9c6a0b40"
CLOUDBASE_FUNCTION = "function-planner-queryplandetail"
CLOUDBASE_DATA_VERSION = "2020-01-10"
REQUEST_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
REQUEST_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.d2core.com",
    "Referer": "https://www.d2core.com/",
    "User-Agent": "Diablo 4 Loot Filter - Profile Importer",
}


class D2CoreClientError(RuntimeError):
    pass


def query_public_build(share_code: str) -> dict[str, object]:
    """Return one public build payload without using a logged-in browser session."""
    request_data = json.dumps({"bd": share_code, "enableVariant": True}, separators=(",", ":"))
    body = {
        "action": "functions.invokeFunction",
        "dataVersion": CLOUDBASE_DATA_VERSION,
        "env": CLOUDBASE_ENV,
        "function_name": CLOUDBASE_FUNCTION,
        "request_data": request_data,
    }
    try:
        response = httpx.post(
            CLOUDBASE_ENDPOINT,
            params={"env": CLOUDBASE_ENV},
            headers=REQUEST_HEADERS,
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as error:
        message = "Could not reach the public D2Core build service"
        raise D2CoreClientError(message) from error
    if response.status_code != 200:
        message = f"D2Core build service returned HTTP {response.status_code}"
        raise D2CoreClientError(message)
    if len(response.content) > MAX_RESPONSE_BYTES:
        message = "D2Core returned an unexpectedly large build response"
        raise D2CoreClientError(message)
    return _parse_cloudbase_response(response.content)


def _parse_cloudbase_response(payload: bytes) -> dict[str, object]:
    root = _decode_json_object(payload, "service response")
    if error_code := root.get("code"):
        message = f"D2Core build service rejected the request: {error_code}"
        raise D2CoreClientError(message)
    envelope = root.get("data")
    if not isinstance(envelope, dict) or not isinstance(response_data := envelope.get("response_data"), str):
        message = "D2Core returned an invalid service response"
        raise D2CoreClientError(message)
    result = _decode_json_object(response_data.encode(), "build response")
    if error_message := result.get("errMsg") or result.get("errmsg"):
        message = f"D2Core could not return this public build: {error_message}"
        raise D2CoreClientError(message)
    build = result.get("data")
    if not isinstance(build, dict):
        message = "D2Core returned no public build data"
        raise D2CoreClientError(message)
    return cast("dict[str, object]", build)


def _decode_json_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: _reject_constant(constant),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        message = f"D2Core returned invalid JSON in its {label}"
        raise D2CoreClientError(message) from error
    if not isinstance(value, dict):
        message = f"D2Core returned an invalid {label}"
        raise D2CoreClientError(message)
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            message = f"Duplicate JSON key: {key}"
            raise ValueError(message)
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    message = f"Non-standard JSON value: {value}"
    raise ValueError(message)
