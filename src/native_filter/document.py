"""Atomic independent documents; regenerating never changes a saved document."""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from src.native_filter.codec import encode_filter
from src.native_filter.compiler import CompilePolicy
from src.native_filter.decoder import decode_filter
from src.native_filter.models import NativeFilter, NativeFilterError
from src.profiles import BuildSourceModel


@dataclass
class SavedDocument:
    document: NativeFilter
    profile_name: str | None = None
    profile_digest: str = ""
    game_version: str = ""
    warnings: tuple[str, ...] = ()
    manually_edited: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: BuildSourceModel | None = None
    generation_policy: CompilePolicy | None = None


def save_document(path: Path, saved: SavedDocument) -> None:
    payload = {
        "schema_version": 1,
        "code": encode_filter(saved.document),
        "profile_name": saved.profile_name,
        "profile_digest": saved.profile_digest,
        "game_version": saved.game_version,
        "warnings": list(saved.warnings),
        "manually_edited": saved.manually_edited,
        "updated_at": datetime.now(UTC).isoformat(),
        "source": saved.source.model_dump(mode="json") if saved.source else None,
        "generation_policy": asdict(saved.generation_policy) if saved.generation_policy else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent, prefix=".native-filter-") as directory:
        temporary = Path(directory) / "document.json"
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)


def load_document(path: Path) -> SavedDocument:
    if path.stat().st_size > 3_000_000:
        msg = "保存的过滤器文件过大"
        raise NativeFilterError(msg)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        msg = "过滤器文件不是有效的 JSON"
        raise NativeFilterError(msg) from error
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("code"), str):
        msg = "不支持的过滤器文件格式"
        raise NativeFilterError(msg)
    profile_name = data.get("profile_name")
    if profile_name is not None and not isinstance(profile_name, str):
        msg = "保存的 Profile 关联无效"
        raise NativeFilterError(msg)
    warnings = data.get("warnings", [])
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        msg = "保存的提示列表无效"
        raise NativeFilterError(msg)
    try:
        source = BuildSourceModel.model_validate(data["source"]) if data.get("source") is not None else None
        policy_data = data.get("generation_policy")
        policy = None
        if policy_data is not None:
            if not isinstance(policy_data, dict) or any(
                not isinstance(value, bool if key in {"filter_equipment", "preserve_sanctified"} else str)
                for key, value in policy_data.items()
            ):
                msg = "保存的生成策略无效"
                raise NativeFilterError(msg)
            policy = CompilePolicy(**policy_data)
    except (ValidationError, TypeError) as error:
        msg = "保存的 Build 来源或生成策略无效"
        raise NativeFilterError(msg) from error
    return SavedDocument(
        decode_filter(data["code"]),
        profile_name,
        str(data.get("profile_digest", "")),
        str(data.get("game_version", "")),
        tuple(warnings),
        bool(data.get("manually_edited", False)),
        str(data.get("updated_at", "")),
        source,
        policy,
    )
