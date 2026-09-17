import pytest

from src.tools.season_data_watch.discovery import D2CoreDiscoveryError, discover_catalog_build


def test_discovers_build_from_index_constant() -> None:
    payloads = {"https://www.d2core.com/": b'const D4_BUILD_VERSION = "73552";'}

    assert discover_catalog_build(payloads.__getitem__, "https://www.d2core.com/") == "73552"


def test_discovers_build_from_same_origin_index_bundle() -> None:
    payloads = {
        "https://www.d2core.com/": b'<script src="/assets/index-current.js"></script>',
        "https://www.d2core.com/assets/index-current.js": b'D4_BUILD_VERSION="73552"',
    }

    assert discover_catalog_build(payloads.__getitem__, "https://www.d2core.com/") == "73552"


def test_rejects_missing_or_ambiguous_build_metadata() -> None:
    payloads = {"https://www.d2core.com/": b"<html></html>"}

    with pytest.raises(D2CoreDiscoveryError, match="discover one"):
        discover_catalog_build(payloads.__getitem__, "https://www.d2core.com/")
