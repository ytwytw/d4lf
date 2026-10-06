import zipfile
from contextlib import nullcontext

import httpx
import pytest

from src.autoupdater import D4LFUpdater, _should_check_for_update, notify_if_update
from src.release_payload import REQUIRED_FILES


def test_normalize_version_adds_prefix_and_preserves_missing_values() -> None:
    assert D4LFUpdater.normalize_version(" 1.2.3") == "v1.2.3"
    assert D4LFUpdater.normalize_version("v1.2.3") == "v1.2.3"
    assert D4LFUpdater.normalize_version(" v1.2.3 ") == "v1.2.3"
    assert D4LFUpdater.normalize_version(None) is None


@pytest.mark.parametrize("failure", [FileNotFoundError("missing CA bundle"), PermissionError("unreadable CA bundle")])
def test_update_notification_does_not_abort_startup_for_unavailable_ca(mocker, caplog, failure) -> None:
    mocker.patch("src.autoupdater._should_check_for_update", return_value=True)
    request = mocker.patch("src.autoupdater.httpx.get", side_effect=failure)

    notify_if_update()

    request.assert_called_once()
    assert "Error fetching release info" in caplog.text
    assert "skipping check for updates" in caplog.text


def test_change_summary_read_error_does_not_abort_update_notification(mocker, caplog) -> None:
    mocker.patch("src.autoupdater._should_check_for_update", return_value=True)
    mocker.patch("src.autoupdater.__version__", "10.0.7+zhcn.1")
    mocker.patch.object(D4LFUpdater, "get_latest_release", return_value={"tag_name": "v10.0.8"})
    mocker.patch("src.autoupdater.httpx.get", side_effect=FileNotFoundError("missing CA bundle"))

    notify_if_update()

    assert "Error fetching changes since last update" in caplog.text


def test_get_latest_release_includes_prereleases_for_beta_versions(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {"tag_name": "v10.0.0-beta6", "prerelease": True},
                {"tag_name": "v10.0.0-beta7", "prerelease": True},
            ]

    requests = []
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.0+zhcn.beta.1")
    monkeypatch.setattr("src.autoupdater.httpx.get", lambda url, **_kwargs: requests.append(url) or Response())

    release = D4LFUpdater().get_latest_release()

    assert release is not None
    assert release["tag_name"] == "v10.0.0-beta7"
    assert requests == ["https://api.github.com/repos/ytwytw/d4lf/releases?per_page=100"]


def test_get_latest_release_allows_beta_versions_to_update_to_final_release(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [{"tag_name": "v10.0.0", "prerelease": False}, {"tag_name": "v10.0.0-beta7", "prerelease": True}]

    monkeypatch.setattr("src.autoupdater.__version__", "10.0.0-beta6")
    monkeypatch.setattr("src.autoupdater.httpx.get", lambda *_args, **_kwargs: Response())

    release = D4LFUpdater().get_latest_release()
    assert release is not None
    assert release["tag_name"] == "v10.0.0"


def test_get_latest_release_uses_stable_endpoint_for_release_versions(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"tag_name": "v10.0.0", "prerelease": False}

    requests = []
    monkeypatch.setattr("src.autoupdater.__version__", "9.9.9")
    monkeypatch.setattr("src.autoupdater.httpx.get", lambda url, **_kwargs: requests.append(url) or Response())

    release = D4LFUpdater().get_latest_release()
    assert release is not None
    assert release["tag_name"] == "v10.0.0"
    assert requests == ["https://api.github.com/repos/ytwytw/d4lf/releases/latest"]


def test_extract_release_writes_version_and_files(tmp_path) -> None:
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as release:
        release.writestr("d4lf/readme.txt", "ready")
        for filename in REQUIRED_FILES:
            release.writestr("d4lf/" + filename, "payload")
    updater = D4LFUpdater()
    updater.temp_dir = tmp_path / "temp_update"
    updater.version_file = updater.temp_dir / "version"

    assert updater.extract_release(archive, "v4.5.6")
    assert (updater.temp_dir / "d4lf/readme.txt").read_text() == "ready"
    assert updater.version_file.read_text() == "v4.5.6"


def test_download_file_writes_streamed_content_without_network(monkeypatch, tmp_path) -> None:
    class Response:
        headers = {"content-length": "5"}

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self, chunk_size):
            assert chunk_size == 8192
            return [b"he", b"llo"]

    monkeypatch.setattr("src.autoupdater.httpx.stream", lambda *_args, **_kwargs: nullcontext(Response()))
    target = tmp_path / "download.zip"

    assert D4LFUpdater.download_file("https://example.invalid/release.zip", target)
    assert target.read_bytes() == b"hello"


@pytest.mark.parametrize("tag", ["v9.0.0", "v10.0.3", "v10.0.3+zhcn.1"])
def test_notification_does_not_offer_equal_or_older_release(monkeypatch, caplog, tag) -> None:
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.3+zhcn.1")
    monkeypatch.setattr("src.autoupdater._should_check_for_update", lambda: True)
    monkeypatch.setattr(D4LFUpdater, "get_latest_release", lambda *_args, **_kwargs: {"tag_name": tag})
    monkeypatch.setattr(
        D4LFUpdater, "print_changes_between_releases", lambda *_args, **_kwargs: pytest.fail("downgrade")
    )
    notify_if_update()
    assert "An update has been detected" not in caplog.text


def test_notification_names_shipped_updater(monkeypatch, caplog) -> None:
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.3+zhcn.1")
    monkeypatch.setattr("src.autoupdater._should_check_for_update", lambda: True)
    monkeypatch.setattr(D4LFUpdater, "get_latest_release", lambda *_args, **_kwargs: {"tag_name": "v10.0.3+zhcn.2"})
    monkeypatch.setattr(D4LFUpdater, "print_changes_between_releases", lambda *_args, **_kwargs: None)
    with caplog.at_level("INFO"):
        notify_if_update()
    assert "Run autoupdater.bat" in caplog.text


@pytest.mark.parametrize("content", [b"not json", b"null", b'{"message":"not a release"}', b'[null, "bad"]'])
def test_bad_release_metadata_is_not_an_update(monkeypatch, content) -> None:
    response = httpx.Response(200, content=content, request=httpx.Request("GET", "https://api.github.com"))
    monkeypatch.setattr("src.autoupdater.httpx.get", lambda *_args, **_kwargs: response)
    assert D4LFUpdater().get_latest_release(silent=True) is None


def test_corrupt_update_timestamp_does_not_break_startup(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/last_update").write_text("invalid", encoding="utf-8")
    assert _should_check_for_update()
    assert not _should_check_for_update()


def test_preprocess_selects_exact_versioned_asset(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.3+zhcn.1")
    updater = D4LFUpdater()
    monkeypatch.setattr(
        updater,
        "get_latest_release",
        lambda: {
            "tag_name": "v10.0.3+zhcn.2",
            "assets": [
                {"name": "d4lf_wrong.zip", "browser_download_url": "https://example.invalid/wrong"},
                {"name": "d4lf_v10.0.3+zhcn.2.zip", "browser_download_url": "https://example.invalid/right"},
            ],
        },
    )
    monkeypatch.setattr(updater, "print_changes_between_releases", lambda *_args: None)
    urls = []
    monkeypatch.setattr(updater, "download_file", lambda url, _path: urls.append(url) or True)
    monkeypatch.setattr(updater, "extract_release", lambda *_args: True)
    assert updater.preprocess()
    assert urls == ["https://example.invalid/right"]


def test_preprocess_refuses_downgrade_without_downloading(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.3+zhcn.1")
    monkeypatch.setattr("builtins.input", lambda *_args: "")
    updater = D4LFUpdater()
    monkeypatch.setattr(updater, "get_latest_release", lambda: {"tag_name": "v10.0.3"})
    monkeypatch.setattr(updater, "download_file", lambda *_args: pytest.fail("must not download downgrade"))
    with pytest.raises(SystemExit) as result:
        updater.preprocess()
    assert result.value.code == 2
    assert not updater.temp_dir.exists()


def test_failed_archive_does_not_write_success_version(tmp_path) -> None:
    updater = D4LFUpdater()
    updater.temp_dir = tmp_path / "temp_update"
    updater.version_file = updater.temp_dir / "version"
    archive = tmp_path / "invalid.zip"
    archive.write_bytes(b"not a zip")
    assert not updater.extract_release(archive, "v10.0.3+zhcn.2")
    assert not updater.version_file.exists()


def test_postprocess_preserves_payload_when_version_did_not_update(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.3+zhcn.1")
    updater = D4LFUpdater()
    updater.temp_dir.mkdir()
    updater.version_file.write_text("v10.0.3+zhcn.2", encoding="utf-8")
    assert not updater.postprocess()
    assert updater.version_file.exists()


def test_postprocess_cleans_only_staging_after_matching_version(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.3+zhcn.2")
    updater = D4LFUpdater()
    updater.temp_dir.mkdir()
    updater.version_file.write_text("v10.0.3+zhcn.2", encoding="utf-8")
    local_file = tmp_path / "notes.txt"
    local_file.write_text("preserve", encoding="utf-8")
    assert updater.postprocess()
    assert not updater.temp_dir.exists()
    assert local_file.read_text(encoding="utf-8") == "preserve"
