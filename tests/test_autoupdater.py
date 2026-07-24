from src import __version__, autoupdater


def test_zhcn_candidate_does_not_query_upstream_releases(mocker) -> None:
    requests_get = mocker.patch.object(autoupdater.requests, "get")
    updater = autoupdater.D4LFUpdater()

    assert "zhcn" in __version__.casefold()
    assert not updater.update_enabled
    assert updater.repo_owner == "ytwytw"
    assert updater.get_latest_release(silent=True) is None
    requests_get.assert_not_called()


def test_zhcn_candidate_skips_periodic_update_state(mocker) -> None:
    should_check = mocker.patch.object(autoupdater, "_should_check_for_update")

    autoupdater.notify_if_update()

    should_check.assert_not_called()
