"""Atomic snapshots in three formats with identical source observations."""

import json
from dataclasses import asdict
from time import sleep
from typing import TYPE_CHECKING, cast

from src.inventory_dump.models import ExportFormat

if TYPE_CHECKING:
    from pathlib import Path

    from src.inventory_dump.models import ScanDocument
    from src.item import Item
    from src.type_aliases import JsonObject


def serialize_item(item: Item) -> JsonObject:
    """Keep every Item field, original text and meaningful enum names."""
    result = asdict(item)
    for key in ("item_type", "rarity", "seasonal_attribute"):
        value = getattr(item, key)
        result[key] = value.value if value is not None else None
    for key in ("affixes", "inherent"):
        for affix in result[key]:
            affix["type"] = affix["type"].name
    return cast("JsonObject", result)


def render_document(document: ScanDocument, output_format: ExportFormat) -> str:
    """Text exports include the full JSON document after the readable overview."""
    payload = json.dumps(asdict(document), ensure_ascii=False, indent=2)
    if output_format is ExportFormat.JSON:
        return payload + "\n"
    heading = "# " if output_format is ExportFormat.MARKDOWN else ""
    lines = [
        f"{heading}D4LF 库存快照 / Inventory snapshot",
        "",
        f"状态 / Status: {document.status}",
        f"开始 / Started: {document.started_at}",
        f"结束 / Finished: {document.finished_at or '-'}",
        f"条目 / Items: {len(document.items)}; 未完成读取 / Incomplete captures: {document.failed_count}",
        f"原文完整但未映射 / Captured without catalog parsing: {document.unparsed_count}",
        "完整原始 TTS、位置、解析结果及失败原因见下方数据。未扫描范围不代表空库存。",
        "All raw TTS, locations, parsed fields and failures are retained below.",
        "",
    ]
    lines.extend(
        f"- {scope.kind}/{scope.page}: {scope.status}; items={scope.observed_items}" for scope in document.scopes
    )
    lines.extend(f"- {issue}" for issue in document.issues)
    for item in document.items:
        name = (
            (item.parsed or {}).get("original_name")
            or (item.parsed or {}).get("name")
            or (item.observed_fields or {}).get("name_text")
            or "未解析 / Unparsed"
        )
        prefix = "## " if output_format is ExportFormat.MARKDOWN else ""
        lines.extend([
            "",
            f"{prefix}{item.location.label} — {name}",
            f"状态 / Status: {item.status}; 收藏 / Favorite: {item.favorite}; 垃圾 / Junk: {item.junk}",
        ])
        if item.error:
            lines.append(f"原因 / Reason: {item.error}")
        lines.extend(["原始 TTS / Raw TTS:", *item.raw_tts])
    lines.extend(["", "完整数据 / Complete data", ""])
    if output_format is ExportFormat.MARKDOWN:
        # A dynamic fence also preserves arbitrary backticks spoken by the game.
        fence = "`" * (max((len(part) for part in payload.split("\n") if set(part) == {"`"}), default=2) + 1)
        lines.extend([fence + "json", payload, fence])
    else:
        lines.append(payload)
    return "\n".join(lines) + "\n"


class SnapshotWriter:
    def __init__(self, path: Path, output_format: ExportFormat) -> None:
        self.path = path
        self.output_format = output_format

    def save(self, document: ScanDocument) -> None:
        """Keep the last complete, readable snapshot if a write is interrupted."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(render_document(document, self.output_format))
            stream.flush()
        # Windows readers and antivirus can briefly hold the destination without
        # FILE_SHARE_DELETE. Keep both snapshots intact while retrying for 2 s.
        for attempt in range(9):
            try:
                temporary.replace(self.path)
            except PermissionError:
                if attempt == 8:
                    raise
                sleep(0.25)
            else:
                return
