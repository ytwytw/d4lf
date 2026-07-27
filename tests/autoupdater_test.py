import zipfile

import pytest

from src.autoupdater import D4LFUpdater


def test_normalize_version_adds_prefix_and_preserves_missing_values():
    assert D4LFUpdater.normalize_version(" 1.2.3") == "v1.2.3"
    assert D4LFUpdater.normalize_version("v1.2.3") == "v1.2.3"
    assert D4LFUpdater.normalize_version(None) is None


def test_get_latest_release_includes_prereleases_for_beta_versions(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v10.0.0-beta6", "prerelease": True},
                {"tag_name": "v10.0.0-beta7", "prerelease": True},
            ]

    requests = []
    monkeypatch.setattr("src.autoupdater.__version__", "10.0.0+zhcn.beta.1")
    monkeypatch.setattr("src.autoupdater.requests.get", lambda url, **_kwargs: requests.append(url) or Response())

    release = D4LFUpdater().get_latest_release()

    assert release["tag_name"] == "v10.0.0-beta7"
    assert requests == ["https://api.github.com/repos/ytwytw/d4lf/releases?per_page=100"]


def test_get_latest_release_allows_beta_versions_to_update_to_final_release(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"tag_name": "v10.0.0", "prerelease": False}, {"tag_name": "v10.0.0-beta7", "prerelease": True}]

    monkeypatch.setattr("src.autoupdater.__version__", "10.0.0-beta6")
    monkeypatch.setattr("src.autoupdater.requests.get", lambda *_args, **_kwargs: Response())

    assert D4LFUpdater().get_latest_release()["tag_name"] == "v10.0.0"


def test_get_latest_release_uses_stable_endpoint_for_release_versions(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"tag_name": "v10.0.0", "prerelease": False}

    requests = []
    monkeypatch.setattr("src.autoupdater.__version__", "9.9.9")
    monkeypatch.setattr("src.autoupdater.requests.get", lambda url, **_kwargs: requests.append(url) or Response())

    assert D4LFUpdater().get_latest_release()["tag_name"] == "v10.0.0"
    assert requests == ["https://api.github.com/repos/ytwytw/d4lf/releases/latest"]


def test_release_candidate_version_is_recognized_as_prerelease() -> None:
    assert D4LFUpdater._is_prerelease("v10.0.0+zhcn.beta.1")
    assert not D4LFUpdater._is_prerelease("v10.0.0+zhcn.1")


@pytest.mark.parametrize(
    ("candidate", "current"),
    [
        ("v10.0.0+zhcn.beta.2", "v10.0.0+zhcn.beta.1"),
        ("v10.0.0+zhcn.rc.1", "v10.0.0+zhcn.beta.9"),
        ("v10.0.0", "v10.0.0+zhcn.beta.1"),
        ("v10.0.0+zhcn.2", "v10.0.0+zhcn.1"),
        ("v11.0.0", "v10.0.0+zhcn.99"),
    ],
)
def test_version_comparison_accepts_only_newer_releases(candidate, current) -> None:
    assert D4LFUpdater.is_newer_version(candidate, current)


@pytest.mark.parametrize(
    ("candidate", "current"),
    [
        ("v10.0.0+zhcn.beta.1", "v10.0.0+zhcn.beta.2"),
        ("v9.3.7", "v10.0.0+zhcn.beta.1"),
        ("v10.0.0+zhcn.beta.1", "v10.0.0+zhcn.beta.1"),
        ("not-a-version", "v10.0.0"),
    ],
)
def test_version_comparison_rejects_downgrades_equal_and_invalid_tags(candidate, current) -> None:
    assert not D4LFUpdater.is_newer_version(candidate, current)


def test_extract_release_writes_version_and_files(tmp_path):
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as release:
        release.writestr("d4lf/readme.txt", "ready")
    updater = D4LFUpdater()
    updater.temp_dir = tmp_path / "temp_update"
    updater.version_file = updater.temp_dir / "version"

    assert updater.extract_release(archive, "v4.5.6")
    assert (updater.temp_dir / "d4lf/readme.txt").read_text() == "ready"
    assert updater.version_file.read_text() == "v4.5.6"


def test_download_file_writes_streamed_content_without_network(monkeypatch, tmp_path):
    class Response:
        headers = {"content-length": "5"}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            assert chunk_size == 8192
            return [b"he", b"llo"]

    monkeypatch.setattr("src.autoupdater.requests.get", lambda *_args, **_kwargs: Response())
    target = tmp_path / "download.zip"

    assert D4LFUpdater.download_file("https://example.invalid/release.zip", target)
    assert target.read_bytes() == b"hello"
