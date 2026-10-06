import pytest

from src.inventory_dump.layout import INVENTORY_PAGES
from src.inventory_dump.templates import icon


@pytest.mark.parametrize("name", [*INVENTORY_PAGES, "stash", "stash_frame"])
def test_embedded_navigation_templates_decode_without_external_files(name: str) -> None:
    image = icon(name)
    assert image.ndim == 2
    assert image.shape[0] >= 8
    assert image.shape[1] >= 20
    assert image.max() > image.min()
