"""Shared loot-filter fixtures: isolated profile directories and a zhCN catalog."""

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from src.game_data import GameCatalog
from src.game_data import catalog as catalog_module
from src.item.filter import Filter
from src.loot import filter as _filter
from src.settings import AspectFilterType, CosmeticFilterType, UnfilteredUniquesType

if TYPE_CHECKING:
    from pathlib import Path


class _Profiles:
    """Write profile files, enable them, and expose the fake settings for later edits."""

    def __init__(self, directory: Path, settings: SimpleNamespace) -> None:
        self.directory = directory
        self.settings = settings

    def __call__(self, **files: str) -> None:
        for name, text in files.items():
            (self.directory / f"{name}.yaml").write_text(text, encoding="utf-8")
        self.settings.general.profiles = list(files)


@pytest.fixture
def profiles(tmp_path, monkeypatch, mocker):
    directory = tmp_path / "profiles"
    directory.mkdir()
    general = SimpleNamespace(
        profiles=[],
        filter_equipment=True,
        filter_sigils=True,
        filter_tributes=True,
        filter_seals=True,
        filter_charms=True,
        handle_cosmetics=CosmeticFilterType.ignore,
        keep_aspects=AspectFilterType.upgrade,
        handle_uniques=UnfilteredUniquesType.favorite,
        ignore_escalation_sigils=True,
        mark_as_favorite=True,
        do_not_junk_ancestral_legendaries=False,
        auto_use_temper_manuals=False,
    )
    settings = SimpleNamespace(user_dir=tmp_path, general=general, save_value=mocker.Mock())
    monkeypatch.setattr(Filter, "_instance", None)
    monkeypatch.setattr("src.item.filter.engine.get_settings", lambda: settings)
    monkeypatch.setattr(_filter, "get_settings", lambda: settings)
    monkeypatch.setattr(_filter, "_DEGRADED_NOTICE", ())
    monkeypatch.setattr(_filter, "capture", lambda: None)
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)

    return _Profiles(directory, settings)


@pytest.fixture
def zh(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    monkeypatch.setattr(GameCatalog, "_instance", catalog)
    return catalog
