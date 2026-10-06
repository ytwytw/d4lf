"""Atomic snapshots in three formats with identical source observations."""

import json
import re
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
    markdown = output_format is ExportFormat.MARKDOWN
    bullet = "- " if markdown else ""
    lines = [
        f"{'# ' if markdown else ''}D4LF 库存快照 / Inventory snapshot",
        "",
        f"{bullet}状态 / Status: {document.status}",
        f"{bullet}开始 / Started: {document.started_at}",
        f"{bullet}结束 / Finished: {document.finished_at or '-'}",
        f"{bullet}条目 / Items: {len(document.items)}; 未完成读取 / Incomplete captures: {document.failed_count}",
        f"{bullet}原文完整但未映射 / Captured without catalog parsing: {document.unparsed_count}",
        f"{bullet}未确认是否为空的槽位 / Unverified slots: {document.unverified_count}",
        "",
        "完整原始 TTS、位置、解析结果及失败原因见下方数据。未扫描范围不代表空库存。",
        "All raw TTS, locations, parsed fields and failures are retained below.",
        "",
    ]
    lines.extend(
        f"- {scope.kind}/{scope.page}: {scope.status}; items={scope.observed_items}; "
        f"empty={scope.empty_slots}; unverified={len(scope.unverified_slots)}"
        for scope in document.scopes
    )
    lines.extend(f"- {_one_line(issue)}" for issue in document.issues)
    for item in document.items:
        name = (
            (item.observed_fields or {}).get("name_text")
            or (item.parsed or {}).get("original_name")
            or (item.parsed or {}).get("name")
            or "未解析 / Unparsed"
        )
        state = [
            f"{bullet}状态 / Status: {item.status}",
            f"{bullet}收藏 / Favorite: {_tri(item.favorite)}",
            f"{bullet}垃圾 / Junk: {_tri(item.junk)}",
        ]
        if item.error:
            state.append(f"{bullet}原因 / Reason: {_one_line(item.error)}")
        lines.extend(["", f"{'## ' if markdown else ''}{item.location.label} — {_one_line(str(name))}", "", *state])
        lines.extend(["", "原始 TTS / Raw TTS:"])
        if markdown:
            # Raw lines stay verbatim inside a fence longer than any backtick run they contain.
            fence = _fence("\n".join(item.raw_tts))
            lines.extend(["", fence + "text", *item.raw_tts, fence])
        else:
            lines.extend(item.raw_tts)
    lines.extend(["", "完整数据 / Complete data", ""])
    if markdown:
        fence = _fence(payload)
        lines.extend([fence + "json", payload, fence])
    else:
        lines.append(payload)
    return "\n".join(lines) + "\n"


def _tri(value: bool | None) -> str:
    return "unknown" if value is None else str(value).lower()


def _one_line(text: str) -> str:
    return " ".join(text.splitlines())


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


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
