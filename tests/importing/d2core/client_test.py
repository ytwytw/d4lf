import json
from types import SimpleNamespace

import httpx
import pytest

from src.importing.d2core import client as client_module


def _service_response(build: object, *, status_code: int = 200) -> SimpleNamespace:
    inner = json.dumps({"data": build}, ensure_ascii=False)
    content = json.dumps({"requestId": "request-id", "data": {"response_data": inner}}).encode()
    return SimpleNamespace(status_code=status_code, content=content)


def test_query_public_build_uses_read_only_public_function(mocker) -> None:
    post = mocker.patch.object(
        client_module.httpx, "post", return_value=_service_response({"title": "Firewall", "variants": []})
    )

    result = client_module.query_public_build("20eK")

    assert result["title"] == "Firewall"
    request = post.call_args
    assert request.args[0] == client_module.CLOUDBASE_ENDPOINT
    assert request.kwargs["params"] == {"env": client_module.CLOUDBASE_ENV}
    assert request.kwargs["json"]["function_name"] == client_module.CLOUDBASE_FUNCTION
    assert json.loads(request.kwargs["json"]["request_data"]) == {"bd": "20eK", "enableVariant": True}
    assert "access_token" not in request.kwargs["json"]


def test_query_public_build_wraps_network_errors(mocker) -> None:
    request = httpx.Request("POST", client_module.CLOUDBASE_ENDPOINT)
    mocker.patch.object(client_module.httpx, "post", side_effect=httpx.ConnectError("offline", request=request))

    with pytest.raises(client_module.D2CoreClientError, match="Could not reach"):
        client_module.query_public_build("20eK")


@pytest.mark.parametrize(
    "content",
    [
        b'{"data":{"response_data":"{\\"data\\":{},\\"data\\":{}}"}}',
        b'{"data":{"response_data":"{\\"errMsg\\":\\"not public\\"}"}}',
        b'{"data":{"response_data":"{\\"data\\":null}"}}',
    ],
)
def test_parse_cloudbase_response_rejects_invalid_or_error_payloads(content: bytes) -> None:
    with pytest.raises(client_module.D2CoreClientError):
        client_module._parse_cloudbase_response(content)
