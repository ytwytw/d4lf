from src.tools import season_data_watch


def test_package_exports_public_monitoring_api() -> None:
    assert season_data_watch.EXIT_OK == 0
    assert season_data_watch.EXIT_DRIFT == 1
    assert season_data_watch.EXIT_INPUT_ERROR == 2
    assert callable(season_data_watch.check_sources)
    assert callable(season_data_watch.load_source_lock)
