import pytest

from src.equipment_knowledge import load_catalog
from src.equipment_knowledge.profile import equipment_for_profile, load_profile_equipment
from src.profiles import (
    AspectUniqueFilterModel,
    DynamicItemFilterModel,
    ItemFilterModel,
    ProfileDocumentStore,
    ProfileModel,
)


def test_profile_link_keeps_known_ids_and_reports_unknown_without_guessing():
    rule = ItemFilterModel.model_construct(
        unique_aspect=[
            AspectUniqueFilterModel.model_construct(name="fists_of_fate"),
            AspectUniqueFilterModel.model_construct(name="unknown_new_unique"),
        ]
    )
    profile = ProfileModel.model_construct(name="Build A", affixes=[DynamicItemFilterModel({"gloves": rule})])
    linked = equipment_for_profile(profile, load_catalog())
    assert linked.unique_ids == frozenset({186283})
    assert linked.unresolved == ("unknown_new_unique",)
    assert profile.affixes[0].root["gloves"].unique_aspect[0].name == "fists_of_fate"


def test_empty_profile_does_not_claim_entire_catalog_as_build_equipment():
    linked = equipment_for_profile(ProfileModel.model_construct(name="Empty"), load_catalog())
    assert linked.unique_ids == frozenset()


@pytest.mark.parametrize("suffix", [".yaml", ".yml"])
def test_saved_profile_link_accepts_both_yaml_extensions(tmp_path, monkeypatch, suffix):
    path = tmp_path / f"My_Build{suffix}"
    path.write_text("{}", encoding="utf-8")
    store = ProfileDocumentStore(tmp_path, full_dump=False)
    monkeypatch.setattr(ProfileDocumentStore, "default", lambda: store)
    linked = load_profile_equipment("My Build", load_catalog())
    assert linked.name == "My Build"
    assert linked.unique_ids == frozenset()
