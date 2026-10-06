import pytest

from src.profiles import ProfileDocumentStore


@pytest.fixture
def temporary_profile_store(tmp_path, monkeypatch) -> ProfileDocumentStore:
    """Save imports into a temporary store instead of the real profile directory.

    Tests that run complete imports must request this (or patch ``ProfileDocumentStore.default``): the profile
    writer does not go through ``builtins.open``, so mocking that does not stop writes to ``~/.d4lf/profiles``.
    """
    store = ProfileDocumentStore(profiles_dir=tmp_path / "profiles", full_dump=False)
    monkeypatch.setattr(ProfileDocumentStore, "default", classmethod(lambda _cls: store))
    return store
