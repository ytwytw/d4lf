import subprocess
from typing import TYPE_CHECKING

from src.tools.public_safety.git_source import git_root, index_items, tree_items

if TYPE_CHECKING:
    from pathlib import Path


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True)


def test_reads_complete_tree_and_staged_index_snapshots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Public Test")
    _git(repo, "config", "user.email", "test@users.noreply.github.com")
    tracked = repo / "tracked.txt"
    tracked.write_text("committed", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")

    tracked.write_text("staged", encoding="utf-8")
    staged = repo / "captures" / "session.jsonl"
    staged.parent.mkdir()
    staged.write_text("private", encoding="utf-8")
    _git(repo, "add", "tracked.txt", "captures/session.jsonl")

    assert git_root(repo) == repo
    assert tree_items("HEAD", cwd=repo) == {"tracked.txt": b"committed"}
    assert index_items(cwd=repo) == {"captures/session.jsonl": b"private", "tracked.txt": b"staged"}
