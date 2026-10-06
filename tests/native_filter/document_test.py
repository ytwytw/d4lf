import pytest

from src.native_filter import (
    CompilePolicy,
    NativeFilter,
    NativeFilterError,
    SavedDocument,
    load_document,
    save_document,
)
from src.profiles import BuildSourceModel


def test_document_keeps_manual_rules_and_profile_association(tmp_path):
    path = tmp_path / "filters" / "custom.json"
    saved = SavedDocument(NativeFilter("独立改动"), "Build A", "digest", "73552", ("需要验收",), True)
    save_document(path, saved)
    loaded = load_document(path)
    assert loaded.document.name == "独立改动"
    assert loaded.profile_name == "Build A"
    assert loaded.profile_digest == "digest"
    assert loaded.manually_edited
    assert loaded.warnings == ("需要验收",)
    assert not list(path.parent.glob("*.tmp"))


def test_source_and_policy_snapshot_survive_without_original_profile(tmp_path):
    saved = SavedDocument(
        NativeFilter(),
        source=BuildSourceModel(
            provider="d2core", url="https://www.d2core.com/d4/planner?bd=test", variant_id="6", variant_name="后期"
        ),
        generation_policy=CompilePolicy(handle_cosmetics="junk", preserve_sanctified=False),
    )
    path = tmp_path / "filter.json"
    save_document(path, saved)
    loaded = load_document(path)
    assert loaded.source == saved.source
    assert loaded.source is not None
    assert loaded.source.variant_id == "6"
    assert loaded.generation_policy == saved.generation_policy


def test_invalid_save_does_not_damage_previous_document(tmp_path):
    path = tmp_path / "existing.json"
    saved = SavedDocument(NativeFilter())
    save_document(path, saved)
    original = path.read_bytes()
    saved.document.rules.clear()
    with pytest.raises(NativeFilterError):
        save_document(path, saved)
    assert path.read_bytes() == original


@pytest.mark.parametrize("text", ['{"schema_version":2,"code":"x"}', "[]", "{oops"])
def test_invalid_document_is_reported(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(NativeFilterError):
        load_document(path)
