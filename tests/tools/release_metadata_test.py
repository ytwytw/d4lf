import re
from typing import TYPE_CHECKING

import pytest

from src import __version__
from src.release_versions import is_prerelease
from src.tools.release_metadata import NOTES_PATH, ROOT, main, release_metadata, render_release_body

if TYPE_CHECKING:
    from pathlib import Path

_CANDIDATE_WORDING = ("尚未发布", "候选版", "has not been published", "not been published yet")


def test_current_release_metadata_matches_updater_asset_and_tag() -> None:
    metadata = release_metadata()
    assert metadata == {
        "version": __version__,
        "tag": f"v{__version__}",
        "prerelease": "false",
        "zip_name": f"d4lf_v{__version__}.zip",
    }


@pytest.mark.parametrize("version", ["10.0.8+zhcn.beta.1", "10.0.8-rc1", "10.0.8alpha2", "10.0.7+zhcn.3", "10.0.8"])
def test_prerelease_flag_uses_updater_version_rules(version) -> None:
    assert release_metadata(version)["prerelease"] == ("true" if is_prerelease(version) else "false")


@pytest.mark.parametrize("version", ["10.0.7-zhcn3", "latest", "10.0", "10.0.7+zhcn.3 beta"])
def test_versions_the_updater_cannot_order_are_rejected(version) -> None:
    with pytest.raises(ValueError, match="cannot be ordered"):
        release_metadata(version)


def _notes(root: Path, text: str) -> Path:
    for name in ("README.md", "docs/guide.md", "assets/shot.png"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x", encoding="utf-8")
    source = root / "docs" / "notes.md"
    source.write_text(text, encoding="utf-8")
    return source


def test_release_body_drops_title_and_makes_repository_links_absolute(tmp_path) -> None:
    source = _notes(
        tmp_path,
        "# 1.0 版本说明\n\n见[说明](guide.md#%E6%95%85)、[README](../README.md)、"
        "[外部](https://example.com/a)和[本页](#top)。\n![图](../assets/shot.png)\n",
    )
    body = render_release_body("owner/repo", "v1.0+zhcn.1", source, tmp_path)
    base = "https://github.com/owner/repo"
    assert not body.startswith("#")
    assert f"[说明]({base}/blob/v1.0%2Bzhcn.1/docs/guide.md#%E6%95%85)" in body
    assert f"[README]({base}/blob/v1.0%2Bzhcn.1/README.md)" in body
    assert "[外部](https://example.com/a)" in body
    assert f"[本页]({base}/blob/v1.0%2Bzhcn.1/docs/notes.md#top)" in body
    assert f"![图]({base}/raw/v1.0%2Bzhcn.1/assets/shot.png)" in body


@pytest.mark.parametrize("target", ["missing.md", "../../outside.md"])
def test_release_body_rejects_links_to_missing_or_outside_files(tmp_path, target) -> None:
    source = _notes(tmp_path, f"[x]({target})\n")
    with pytest.raises(ValueError, match="does not point to a repository file"):
        render_release_body("owner/repo", "v1", source, tmp_path)


@pytest.mark.parametrize("repository", ["owner", "owner/repo/extra", "https://github.com/owner/repo", ""])
def test_release_body_requires_owner_and_name(tmp_path, repository) -> None:
    with pytest.raises(ValueError, match="Invalid GitHub repository"):
        render_release_body(repository, "v1", _notes(tmp_path, "text\n"), tmp_path)


def test_shipped_release_notes_render_without_relative_links_or_candidate_wording() -> None:
    body = render_release_body("ytwytw/d4lf", f"v{__version__}")
    targets = re.findall(r"\]\(([^)\s]+)\)", body)
    assert targets
    assert all(target.startswith("https://") for target in targets)
    assert not any(phrase in body for phrase in _CANDIDATE_WORDING)


def test_user_docs_name_current_version_without_unpublished_wording() -> None:
    assert NOTES_PATH.read_text(encoding="utf-8").startswith(f"# {__version__} ")
    for name in ("README.md", "README.en.md", "docs/release-notes.zh-CN.md", "docs/loot-tools.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert not any(phrase in text for phrase in _CANDIDATE_WORDING), name
    for name in ("README.md", "README.en.md"):
        assert f"`{__version__}`" in (ROOT / name).read_text(encoding="utf-8"), name


def test_cli_appends_github_outputs_and_writes_notes(tmp_path) -> None:
    output = tmp_path / "github_output"
    output.write_text("existing=1\n", encoding="utf-8")
    assert main(["github-output", str(output)]) == 0
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "existing=1"
    assert f"tag=v{__version__}" in lines
    assert "prerelease=false" in lines
    notes = tmp_path / "body.md"
    assert main(["notes", "--repository", "ytwytw/d4lf", "--ref", f"v{__version__}", "--output", str(notes)]) == 0
    assert "https://github.com/ytwytw/d4lf/" in notes.read_text(encoding="utf-8")
    assert main(["notes", "--repository", "bad", "--ref", "v1", "--output", str(notes)]) == 1
