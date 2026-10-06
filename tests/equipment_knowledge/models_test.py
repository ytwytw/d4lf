import pytest
from pydantic import ValidationError

from src.equipment_knowledge.models import AffixEntry


def test_raw_unknown_source_fields_survive_without_fabricated_translation():
    record = AffixEntry(sno_id=17, key="new", name_en="New", raw_en={"new_field": {"value": None}})
    assert record.name_zh is None
    assert record.raw_zh is None
    assert AffixEntry.model_validate_json(record.model_dump_json()) == record
    with pytest.raises(ValidationError, match="Extra inputs"):
        AffixEntry.model_validate({**record.model_dump(), "unsupported_schema_field": 1})
