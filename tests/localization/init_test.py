from src.localization import translate


def test_package_exports_translate() -> None:
    assert callable(translate)
