import pytest

from src.importing import UnsupportedImportSourceError, select_source


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("https://maxroll.gg/x", "maxroll"),
        ("https://d4builds.gg/x", "d4builds"),
        ("https://www.d2core.com/d4/planner?bd=20eK", "d2core"),
    ],
)
def test_select_source_uses_public_adapter_facades(url: str, name: str) -> None:
    assert select_source(url).name == name


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid/build",
        "https://d2core.com.example.invalid/d4/planner?bd=x",
        "https://untrusted.d2core.com/d4/planner?bd=x",
    ],
)
def test_select_source_rejects_unknown_hosts(url: str) -> None:
    with pytest.raises(UnsupportedImportSourceError):
        select_source(url)
