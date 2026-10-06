"""Write checksummed small parts instead of a large opaque generated asset."""

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from src.equipment_knowledge.models import KnowledgeData
    from src.type_aliases import JsonObject

_MAX_PART_BYTES = 450_000


def _formatted_bytes(value: JsonObject) -> bytes:
    # Match pretty-format-json in prek.toml before counting bytes or hashing.
    return (json.dumps(value, ensure_ascii=False, indent=4, sort_keys=True) + "\n").encode("utf-8")


def write_snapshot(data: KnowledgeData, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json")
    parts = []
    for field in ("items", "affixes"):
        rows = payload.pop(field)
        payload[field] = []
        chunks: list[list[JsonObject]] = [[]]
        for row in rows:
            if len(_formatted_bytes({field: [row]})) > _MAX_PART_BYTES:
                msg = "A single knowledge record exceeds the asset size budget"
                raise ValueError(msg)
            if chunks[-1] and len(_formatted_bytes({field: [*chunks[-1], row]})) > _MAX_PART_BYTES:
                chunks.append([])
            chunks[-1].append(row)
        for number, rows in enumerate(chunks, start=1):
            name = f"{output.stem}-{field}-{number:02}.json"
            content = _formatted_bytes({field: rows})
            (output.parent / name).write_bytes(content)
            parts.append({
                "path": name,
                "field": field,
                "sha256": hashlib.sha256(content).hexdigest(),
                "records": len(rows),
            })
    payload["parts"] = parts
    output.write_bytes(_formatted_bytes(payload))
