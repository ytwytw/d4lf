from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from src.tools.public_safety import cli


def test_index_failure_is_actionable_and_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    token = "ghp_" + "a" * 36
    monkeypatch.setattr(cli, "git_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "index_items", lambda **_kwargs: {"notes.txt": token.encode()})

    assert cli.main(["--index"]) == 1

    error = capsys.readouterr().err
    assert "[github-token] notes.txt:1" in error
    assert "rotate" in error
    assert token not in error


def test_tree_success_reports_scanned_file_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "git_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "tree_items", lambda _revision, **_kwargs: {"README.md": b"public"})

    assert cli.main(["--tree", "HEAD"]) == 0
    assert "passed (1 files)" in capsys.readouterr().out


def test_local_denylist_is_optional_and_never_echoed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    private_term = "private-handle"
    denylist = tmp_path / ".public-safety.local"
    denylist.write_text(f"# local only\n{private_term}\n", encoding="utf-8")
    monkeypatch.setattr(cli, "git_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "index_items", lambda **_kwargs: {"metadata.txt": private_term.encode()})

    assert cli.main(["--index"]) == 1
    assert private_term not in capsys.readouterr().err
