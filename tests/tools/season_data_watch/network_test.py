import httpx
import pytest

from src.tools.season_data_watch import network


@pytest.mark.parametrize(
    "url",
    [
        "http://www.d2core.com/",
        "https://127.0.0.1/data",
        "https://user@www.d2core.com/",
        "https://www.d2core.com:444/",
        "https://www.d2core.com/#fragment",
    ],
)
def test_validate_source_url_rejects_untrusted_locations(url: str) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        network.validate_source_url(url)


def test_fetch_source_reads_allowlisted_https_response(mocker) -> None:
    payload = b"season data"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload, request=request))
    client_type = httpx.Client
    mocker.patch.object(
        network.httpx, "Client", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs)
    )

    assert network.fetch_source("https://raw.githubusercontent.com/example/data/main/build.txt") == payload
    assert network.sha256_hex(payload) == "65047a1b97582861fde0d4c41fc9f86a63151a96cbb2aed5c1f8c74b1c9c8886"


def test_fetch_source_rejects_oversized_response(mocker) -> None:
    payload = b"x" * 9
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload, request=request))
    client_type = httpx.Client
    mocker.patch.object(network, "MAX_SOURCE_BYTES", 8)
    mocker.patch.object(
        network.httpx, "Client", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs)
    )

    with pytest.raises(ValueError, match="exceeds"):
        network.fetch_source("https://www.d2core.com/data")
