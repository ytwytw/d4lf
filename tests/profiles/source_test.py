from src.profiles import BuildSourceModel, ProfileDocumentStore, ProfileModel


def test_source_identity_survives_edit_and_rename(tmp_path):
    store = ProfileDocumentStore(profiles_dir=tmp_path, full_dump=False)
    source = BuildSourceModel(
        provider="d2core",
        url="https://www.d2core.com/d4/planner?bd=22XD&var=6",
        variant_id="6",
        variant_name="同名变体",
        build_title="幻影尖啸",
        season="15",
    )
    profile = ProfileModel(name="imported", source=source)
    original = store.save_new(file_name="original", profile=profile, source=source.url)
    loaded = store.load(original.path)
    loaded.profile.name = "edited"
    store.save_existing(loaded=loaded, profile=loaded.profile, source="custom")
    assert store.load(original.path).profile.source == source
    renamed = store.save_new(file_name="renamed", profile=loaded.profile, source="custom")
    assert store.load(renamed.path).profile.source == source


def test_existing_profile_does_not_invent_build_identity(tmp_path):
    path = tmp_path / "old.yaml"
    path.write_text("Affixes: []\n", encoding="utf-8")
    store = ProfileDocumentStore(profiles_dir=tmp_path, full_dump=False)
    assert store.load(path).profile.source is None
