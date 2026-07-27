"""Constrained network access for seasonal source checks."""

import hashlib
from urllib.parse import urlsplit

import httpx

ALLOWED_SOURCE_HOSTS = frozenset({
    "cloudstorage.d2core.com",
    "d2core.com",
    "raw.githubusercontent.com",
    "www.d2core.com",
})
MAX_SOURCE_BYTES = 32 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 30


def validate_source_url(url: str) -> None:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in ALLOWED_SOURCE_HOSTS
        or parts.username is not None
        or parts.password is not None
        or parts.port not in {None, 443}
        or parts.fragment
    ):
        message = f"source URL is not allowed: {url}"
        raise ValueError(message)


def fetch_source(url: str) -> bytes:
    validate_source_url(url)
    try:
        with (
            httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > MAX_SOURCE_BYTES:
                    message = f"source response exceeds {MAX_SOURCE_BYTES} bytes: {url}"
                    raise ValueError(message)
            return bytes(payload)
    except httpx.HTTPError as error:
        message = f"could not fetch source URL {url}: {error}"
        raise ValueError(message) from error


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
