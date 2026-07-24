from __future__ import annotations

from typing import TYPE_CHECKING

import build

if TYPE_CHECKING:
    from pathlib import Path


def test_release_bundle_includes_third_party_notices(monkeypatch, tmp_path: Path) -> None:
    copied: list[str] = []
    copied_trees: list[tuple[str, Path]] = []
    monkeypatch.setattr(build.shutil, "copy", lambda source, _destination: copied.append(source))
    monkeypatch.setattr(
        build.shutil, "copytree", lambda source, destination: copied_trees.append((source, destination))
    )

    build.copy_additional_resources(tmp_path)

    assert "LICENSE.txt" in copied
    assert "THIRD-PARTY-NOTICES.md" in copied
    assert ("assets", tmp_path / "assets") in copied_trees
    assert ("docs", tmp_path / "docs") in copied_trees
