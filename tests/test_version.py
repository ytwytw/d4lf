from packaging.version import Version

from src import __version__


def test_application_version_is_pep440_canonical() -> None:
    assert str(Version(__version__)) == __version__
