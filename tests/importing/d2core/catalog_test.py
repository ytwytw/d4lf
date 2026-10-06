from typing import TYPE_CHECKING, cast, override

import httpx
import pytest

from src.game_data import ItemType
from src.importing.d2core.catalog import CatalogStore, CatalogTransport, canonical_affix_name, validate_catalog
from src.importing.d2core.errors import D2CoreCatalogError

if TYPE_CHECKING:
    from src.type_aliases import JsonValue


def test_talisman_catalog_indexes_nested_affixes() -> None:
    catalog = validate_catalog(
        "talisman",
        {
            "charm": [{"key": "charm-key"}],
            "seal": [{"key": "seal-key"}],
            "itemSets": {"set-key": {"name": "Set"}},
            "affixes": {"charm": [{"key": "charm-affix"}], "seal": [{"key": "seal-affix"}]},
        },
    )
    charms = cast("dict[str, dict[str, JsonValue]]", catalog["charm"])
    affixes = cast("dict[str, dict[str, dict[str, JsonValue]]]", catalog["affixes"])
    assert charms["charm-key"]["key"] == "charm-key"
    assert affixes["seal"]["seal-affix"]["key"] == "seal-affix"


def test_catalog_schema_failure_is_not_retried() -> None:
    class Transport(CatalogTransport):
        calls = 0

        @override
        def get(self, url: str, *, timeout: float) -> JsonValue:
            del url, timeout
            self.calls += 1
            return {"not": "an affix catalog"}

    transport = Transport()
    store = CatalogStore(version="v1", transport=transport, sleeper=lambda _: None)
    with pytest.raises(D2CoreCatalogError):
        store.require("affix")
    assert transport.calls == 1


def test_catalog_requests_are_bounded_to_three_attempts_and_ten_seconds() -> None:
    class Transport(CatalogTransport):
        calls = 0
        timeouts: list[float] = []

        @override
        def get(self, url: str, *, timeout: float) -> JsonValue:
            del url
            self.calls += 1
            self.timeouts.append(timeout)
            message = "offline"
            raise httpx.ConnectError(message, request=httpx.Request("GET", "https://example.invalid"))

    transport = Transport()
    sleeps: list[float] = []
    store = CatalogStore(version="v1", transport=transport, sleeper=sleeps.append, attempts=99, timeout=99)

    with pytest.raises(D2CoreCatalogError):
        store.require("affix")

    assert transport.calls == 3
    assert transport.timeouts == [10.0, 10.0, 10.0]
    assert sleeps == [0.05, 0.1]


def test_paragon_catalog_requires_board_node_and_glyph_collections() -> None:
    with pytest.raises(ValueError, match="paragon collections missing"):
        validate_catalog("paragon", {"Druid": {"board": {}}})
    catalog = validate_catalog("paragon", {"Druid": {"board": {}, "node": {}, "glyph": {}}})
    assert "Druid" in catalog


@pytest.mark.parametrize(
    ("desc", "item_type", "expected"),
    [
        ("+[1,226 - 1,450] Maximum Life", None, "maximum_life"),
        ("+[8.0 - 12.0]% Total Armor", None, "total_armor"),
        ("+[2 - 3] to Brand New Skills", None, None),  # unknown description: unresolved, never a near label
        ("+[10.0 - 14.0]% Maximum Life", ItemType.HoradricSeal, "maximum_life"),
        ("+[1 - 2] to All Skills", ItemType.HoradricSeal, None),  # equipment wording, no seal label
    ],
)
def test_canonical_affix_name_requires_an_exact_english_label(desc, item_type, expected) -> None:
    assert canonical_affix_name({"key": "k", "desc": desc}, item_type) == expected
    assert canonical_affix_name({"key": "k"}, item_type) is None
