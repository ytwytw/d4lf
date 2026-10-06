"""Build a separate offline knowledge snapshot from explicitly supplied local sources."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.equipment_knowledge.catalog import canonical_name
from src.equipment_knowledge.models import KnowledgeData
from src.tools.equipment_knowledge_snapshot import write_snapshot

if TYPE_CHECKING:
    from src.type_aliases import JsonObject, JsonValue


def read_json(path: Path) -> JsonValue:
    return cast("JsonValue", json.loads(path.read_text(encoding="utf-8")))


def mapping(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        msg = "Expected a source object"
        raise ValueError(msg)
    return cast("JsonObject", value)


def records(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list):
        msg = "Expected source records"
        raise ValueError(msg)
    return [mapping(row) for row in value]


def text_value(row: JsonObject, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        msg = f"Missing source text: {key}"
        raise ValueError(msg)
    return value


def identity(row: JsonObject) -> tuple[str, int]:
    key, sno = row.get("key"), row.get("id")
    if not isinstance(key, str) or not isinstance(sno, int):
        msg = "Source identity requires a key and integer SNO"
        raise ValueError(msg)
    return key, sno


def pair_rows(en: list[JsonObject], zh: list[JsonObject]) -> list[tuple[JsonObject, JsonObject]]:
    # Repeated affixes use the same identity with different class/slot contexts.
    buckets: dict[tuple[str, int], list[JsonObject]] = defaultdict(list)
    for row in zh:
        buckets[identity(row)].append(row)
    pairs = []
    for row in en:
        candidates = buckets[identity(row)]
        match = next(
            (
                i
                for i, other in enumerate(candidates)
                if other.get("charType") == row.get("charType") and other.get("itemType") == row.get("itemType")
            ),
            None,
        )
        if match is None:
            msg = f"Missing matching Chinese identity/context: {identity(row)}"
            raise ValueError(msg)
        pairs.append((row, candidates.pop(match)))
    if any(buckets.values()):
        msg = "Unpaired Chinese source records"
        raise ValueError(msg)
    return pairs


def d2core_source(root: Path, filename: str, content: bytes) -> JsonObject:
    source: JsonObject = {
        "provider": "D2Core",
        "file": filename,
        "url": f"https://cloudstorage.d2core.com/data/d4/73552/{filename}?env=prod&v=8",
        "sha256": hashlib.sha256(content).hexdigest(),
        "build": "73552",
        "public_redistribution": "unverified",
        "scope": "private development and integration",
    }
    reference = "assets/equipment_knowledge/sources/d2core-redistribution-permission-20261005.json"
    path = root / reference
    permission = mapping(read_json(path)) if path.exists() else {}
    files = permission.get("files")
    approved = files.get(filename) if isinstance(files, dict) else None
    if (
        permission.get("provider") == "D2Core"
        and permission.get("confirmation_type") == "project_user_statement"
        and permission.get("public_redistribution") == "verified"
        and isinstance(approved, dict)
        and all(approved.get(key) == source[key] for key in ("sha256", "build", "url"))
    ):
        source.update({
            "public_redistribution": "verified",
            "public_redistribution_evidence": f"{reference}#/files/{filename}",
            "public_redistribution_basis": "project_user_statement",
            "scope": "public redistribution of this exact source payload with D4LF",
        })
    return source


def redistribution_notice(sources: list[JsonObject]) -> str:
    d2core_sources = [source for source in sources if source.get("provider") == "D2Core"]
    if d2core_sources and all(source.get("public_redistribution") == "verified" for source in d2core_sources):
        return "D2Core 公共再分发许可仅适用于用户已确认的来源哈希范围；依据见 sources，与软件许可证分开记录。"
    return "D2Core 公共再分发授权未全部确认；未匹配许可哈希的来源仅限本地开发与集成。"


def native_affixes(d4data: Path, root: Path) -> tuple[dict[str, list[int]], dict[str, str], JsonObject]:
    native_path = root / "assets/equipment_knowledge/sources/native-affixes.json"
    source = mapping(read_json(native_path))
    index: dict[str, set[int]] = defaultdict(set)
    names: dict[str, str] = {}
    verified: list[JsonObject] = []
    rejected: list[str] = []
    current = mapping(read_json(root / "assets/lang/enUS/affixes.json"))
    for row in records(source["affixes"]):
        key = text_value(row, "sno")
        sno = int(text_value(row, "hash"), 16)
        definition = d4data / "json/base/meta/Affix" / f"{key}.aff.json"
        if not definition.exists() or mapping(read_json(definition)).get("__snoID__") != sno:
            rejected.append(key)
            continue
        verified.append({"key": key, "sno_id": sno, "sha256": hashlib.sha256(definition.read_bytes()).hexdigest()})
        aliases = row.get("keys", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    normalized = alias.replace("-", "_")
                    index[normalized].add(sno)
                    if normalized in current and key not in names:
                        names[key] = normalized
    # Previously round-tripped user fixture, independently verified against this d4data build.
    fixture = {
        "willpower": ("CoreStat_Willpower", 583654),
        "maximum_life": ("Life", 577173),
        "to_hellfire_skills": ("X2_SkillRankBonus_Warlock_Category_Hellfire", 2534852),
    }
    for name, (key, sno) in fixture.items():
        definition = d4data / "json/base/meta/Affix" / f"{key}.aff.json"
        if mapping(read_json(definition)).get("__snoID__") != sno:
            msg = f"Golden native identity mismatch: {key}"
            raise ValueError(msg)
        index[name].add(sno)
        verified.append({
            "key": key,
            "sno_id": sno,
            "sha256": hashlib.sha256(definition.read_bytes()).hexdigest(),
            "evidence": "User's 2026-10-01 InfinityBuilds round-trip fixture + local d4data",
        })
    metadata: JsonObject = {
        "provider": "Freitag47/diablo4-lootfilter-generator + ThunderEagle/D4LootBench",
        **mapping(read_json(native_path.with_name("native-affixes-source.json"))),
        "sha256_scope": "original downloaded source bytes",
        "bundled_file": "sources/native-affixes.json",
        "bundled_sha256": hashlib.sha256(native_path.read_bytes()).hexdigest(),
        "upstream_metadata": source.get("_meta"),
        "verified_definitions": verified,
        "rejected_keys": rejected,
        "license": "MIT for the community data compilation; game rights separate",
    }
    return {key: sorted(value) for key, value in index.items()}, names, metadata


def build_snapshot(root: Path, d2core: Path, d4data: Path, snapshot_date: str) -> KnowledgeData:
    build = (d4data / "buildVersion.txt").read_text(encoding="utf-8").strip()
    if build != "3.2.1.73552":
        msg = f"Expected the pinned d4data build 3.2.1.73552, got {build}"
        raise ValueError(msg)
    sources: list[JsonObject] = []
    payloads = {}
    for family in ("uniqueItem", "affix"):
        for locale in ("enUS", "zhCN"):
            filename = f"{family}_{locale}.json"
            path = d2core / filename
            payloads[filename] = read_json(path)
            sources.append(d2core_source(root, filename, path.read_bytes()))
    native_ids, native_names, native_source = native_affixes(d4data, root)
    sources.append(native_source)
    items = []
    for en, zh in pair_rows(records(payloads["uniqueItem_enUS.json"]), records(payloads["uniqueItem_zhCN.json"])):
        key, sno = identity(en)
        items.append({
            "sno_id": sno,
            "key": key,
            "canonical_name": canonical_name(text_value(en, "name")),
            "name_en": en["name"],
            "name_zh": zh.get("name"),
            "item_type": en["equipType"],
            "raw_en": en,
            "raw_zh": zh,
        })
    affixes = []
    for en, zh in pair_rows(
        records(mapping(payloads["affix_enUS.json"])["affix"]), records(mapping(payloads["affix_zhCN.json"])["affix"])
    ):
        key, sno = identity(en)
        affixes.append({
            "sno_id": sno,
            "key": key,
            "canonical_name": native_names.get(key),
            "name_en": en["desc"],
            "name_zh": zh.get("desc"),
            "raw_en": en,
            "raw_zh": zh,
        })
    types_en = mapping(read_json(root / "assets/lang/enUS/item_types.json"))
    types_zh = mapping(read_json(root / "assets/lang/zhCN/item_types.json"))
    labels: dict[str, tuple[str, str | None, str]] = {}
    for key, name in types_en.items():
        if isinstance(name, str) and not name.startswith("custom type"):
            zh_name = types_zh.get(key)
            labels[key] = (name, zh_name if isinstance(zh_name, str) and zh_name else None, name)
    for item in items:
        en, zh = mapping(item["raw_en"]), mapping(item["raw_zh"])
        key = text_value(en, "equipType")
        if key not in labels:
            label = text_value(en, "equipTypeName")
            labels[key] = (label, text_value(zh, "equipTypeName"), label.lower())
    types, type_provenance = [], []
    for key, (en, zh, canonical) in labels.items():
        path = d4data / "json/base/meta/ItemType" / f"{key}.itt.json"
        if not path.exists():
            continue
        sno = mapping(read_json(path)).get("__snoID__")
        if not isinstance(sno, int):
            msg = f"Missing item type SNO: {path}"
            raise ValueError(msg)
        types.append({"sno_id": sno, "key": key, "canonical_name": canonical, "name_en": en, "name_zh": zh})
        type_provenance.append({"key": key, "sno_id": sno, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    sources.append({
        "provider": "DiabloTools/d4data",
        "build": build,
        "commit": "33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0",
        "url": "https://github.com/DiabloTools/d4data/tree/33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0",
        "item_type_definitions": type_provenance,
        "rights": "Game data rights remain separate from software",
    })
    return KnowledgeData.model_validate({
        "schema_version": 1,
        "game_version": build,
        "snapshot_date": snapshot_date,
        "source": "D2Core 73552 paired enUS/zhCN + DiabloTools/d4data + verified community native-affix index",
        "sources": sources,
        "items": items,
        "affixes": affixes,
        "item_types": types,
        "native_affix_ids": native_ids,
        "limitations": [
            "此包是离线版本快照，不能代表当前游戏或保证全部装备均已收录。",
            "掉落来源缺项为未知；没有掉率或保底概率数据。",
            "英文新增元数据可能尚无中文对应；不以英文冒充中文。",
            redistribution_notice(sources),
            "原生词缀索引源自 3.1.0.72592；本包校验 73552 的 ID/key，不声称游戏规则兼容性已经实测。",
        ],
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d2core-dir", type=Path, required=True)
    parser.add_argument("--d4data-dir", type=Path, required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    data = build_snapshot(args.root, args.d2core_dir, args.d4data_dir, args.snapshot_date)
    output = args.root / "assets/equipment_knowledge/catalog-73552.json"
    write_snapshot(data, output)
    print(f"{output}: {len(data.items)} items, {len(data.affixes)} affixes, {len(data.item_types)} item types")


if __name__ == "__main__":
    main()
