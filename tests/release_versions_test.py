import pytest

from src.release_versions import is_newer_version, select_latest_release, version_key


@pytest.mark.parametrize(
    ("newer", "older"),
    [
        ("v10.0.0+zhcn.beta.2", "v10.0.0+zhcn.beta.1"),
        ("v10.0.0+zhcn.rc.1", "v10.0.0+zhcn.beta.9"),
        ("v10.0.0", "v10.0.0+zhcn.rc.9"),
        ("v10.0.0+zhcn.2", "v10.0.0+zhcn.1"),
        ("v10.0.3+zhcn.1", "v10.0.3"),
        ("v10.0.4", "v10.0.3+zhcn.9"),
    ],
)
def test_release_versions_order_prereleases_and_zhcn_revisions(newer, older) -> None:
    assert is_newer_version(newer, older)
    newer_key = version_key(newer)
    older_key = version_key(older)
    assert newer_key is not None
    assert older_key is not None
    assert newer_key > older_key


def test_select_latest_release_ignores_drafts_and_list_order() -> None:
    releases: list[dict[str, object]] = [
        {"tag_name": "v10.0.0+zhcn.beta.1"},
        {"tag_name": "v11.0.0", "draft": True},
        {"tag_name": "v10.0.0+zhcn.beta.3"},
        {"tag_name": "v10.0.0+zhcn.beta.2"},
    ]

    assert select_latest_release(releases) == {"tag_name": "v10.0.0+zhcn.beta.3"}


@pytest.mark.parametrize("tag", ["nonsense", "v99.0.0-garbage", "v99.0.0+zhcn.not-a-release", "v10.0.3/../../bad"])
def test_invalid_tags_are_never_selected(tag) -> None:
    assert version_key(tag) is None
    assert select_latest_release([{"tag_name": tag}]) is None
