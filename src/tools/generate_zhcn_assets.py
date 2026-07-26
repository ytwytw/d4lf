from __future__ import annotations

# Detailed source paths make generator failures actionable.
# ruff: noqa: EM101, EM102
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.locale_data import LocaleGrammar
from src.tools import companion_data, d2core_data

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
RUNTIME_FILES = (
    "affixes.json",
    "aspects.json",
    "charms_affixes.json",
    "corrections.json",
    "grammar.json",
    "item_types.json",
    "seals_affixes.json",
    "sets.json",
    "sigils.json",
    "tooltips.json",
    "tributes.json",
    "uniques.json",
)
_ITEM_RARITY_NAMES = {
    "Normal": "Common",
    "Magic": "Magic",
    "Rare": "Rare",
    "Legendary": "Legendary",
    "Unique": "Unique",
    "Mythic": "Mythic",
    "Set": "Set",
}
_SIGIL_SECTIONS = {"Dungeon": "dungeons", "Major": "major", "Minor": "minor", "Positive": "positive"}
_NON_FILTERABLE_ITEM_TYPES = frozenset({"Elixir", "Incense", "Material", "TemperManual", "Tome"})


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GeneratedBundle:
    output_dir: Path
    catalog_dir: Path
    quality_report: Path
    locale_manifest: Path
    source_lock: Path
    runtime_ready: bool


@dataclass(frozen=True, slots=True)
class _TranslationCandidate:
    text: str
    provider: str
    source_id: str
    source_record_sha256: str

    def source_record(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "source_id": self.source_id,
            "source_record_sha256": self.source_record_sha256,
            "translation_sha256": _sha256_text(self.text),
        }


def _load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GenerationError(f"missing {label}: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GenerationError(f"{label} is not valid UTF-8 JSON: {path}: {exc}") from exc


def _json_object(path: Path, label: str) -> dict[str, object]:
    value = _load_json(path, label)
    if not isinstance(value, dict):
        raise GenerationError(f"{label} must contain a JSON object: {path}")
    return cast("dict[str, object]", value)


def _json_array(path: Path, label: str) -> list[object]:
    value = _load_json(path, label)
    if not isinstance(value, list):
        raise GenerationError(f"{label} must contain a JSON array: {path}")
    return cast("list[object]", value)


def _canonical_json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=4, sort_keys=True, allow_nan=False) + "\n"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json_text(payload), encoding="utf-8", newline="\n")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _template_identity(value: str) -> str:
    """Normalize a localized template while ignoring source-specific numeric values."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalpha())


def _exact_index_identity(value: str) -> str:
    identity = _identity(value)
    return f"exact:{identity}" if identity else ""


def _template_index_identity(value: str) -> str:
    identity = _template_identity(value)
    return f"template:{identity}" if identity else ""


def _index_identities(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            identity for identity in (_exact_index_identity(value), _template_index_identity(value)) if identity
        )
    )


def _numeric_template_text(value: str) -> str:
    """Remove source-instance values when a generic stable template matched."""
    normalized = re.sub(r"\d+(?:[.,，．]\d+)*\s*[-–—]\s*\d+(?:[.,，．]\d+)*\s*[%％]?", "", value)
    normalized = re.sub(r"\d+(?:[.,，．]\d+)*\s*[%％]?", "", normalized)
    return " ".join(normalized.split())


def _is_ascii_placeholder(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and stripped.isascii() and any(character.isalpha() for character in stripped)


def _select_translation(candidates: Iterable[str]) -> tuple[str | None, str | None]:
    values = {value.strip() for value in candidates if value.strip()}
    translated = {value for value in values if not _is_ascii_placeholder(value)}
    if not translated:
        return None, "ascii_placeholder" if values else "missing_translation"

    groups: dict[str, set[str]] = defaultdict(set)
    for value in translated:
        groups[_identity(value)].add(value)
    groups.pop("", None)
    if len(groups) != 1:
        return None, "ambiguous_translation"

    values_in_group = next(iter(groups.values()))
    return min(
        values_in_group, key=lambda value: (sum(not character.isalnum() for character in value), len(value), value)
    ), None


def _translation_index(entries: Sequence[companion_data.CanonicalEntry], kind: str) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        if entry.kind != kind:
            continue
        chinese = entry.locale_aliases.get("zhCN", ())
        for english in entry.locale_aliases.get("enUS", ()):
            for identity in _index_identities(english):
                index[identity].update(chinese)
    return index


def _canonical_record_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return _sha256_text(encoded)


def _paired_d2core_records(
    snapshot: d2core_data.D2CoreSnapshot, dataset: str
) -> list[tuple[dict[str, object], dict[str, object], int]]:
    field = {"affix": "descTpl", "aspect": "name", "uniqueItem": "name", "talisman": "text"}[dataset]
    grouped: dict[str, dict[tuple[str, int], list[dict[str, object]]]] = {
        "enUS": defaultdict(list),
        "zhCN": defaultdict(list),
    }
    for locale in ("enUS", "zhCN"):
        for row in snapshot.records[dataset, locale]:
            grouped[locale][cast("str", row["key"]), cast("int", row["id"])].append(row)

    pairs: list[tuple[dict[str, object], dict[str, object], int]] = []
    for identity in sorted(grouped["enUS"]):
        english_rows = grouped["enUS"][identity]
        chinese_rows = grouped["zhCN"].get(identity, [])
        if len(english_rows) != len(chinese_rows):
            raise GenerationError(f"D2Core {dataset} locale pair count differs for {identity}")
        english_values = {cast("str", row[field]) for row in english_rows}
        chinese_values = {cast("str", row[field]) for row in chinese_rows}
        if len(english_values) != 1 or len(chinese_values) != 1:
            raise GenerationError(f"D2Core {dataset} duplicate identity {identity} has ambiguous localized records")
        pairs.append((english_rows[0], chinese_rows[0], len(english_rows)))
    return pairs


_D2CORE_FORMULA_PATTERN = re.compile(r"\[[^\[\]]*\]|\{[^{}]*\}")


def _clean_d2core_affix(value: str) -> str:
    cleaned = _D2CORE_FORMULA_PATTERN.sub("", unicodedata.normalize("NFKC", value))
    cleaned = "".join(character if character.isalpha() or character.isspace() else " " for character in cleaned)
    return " ".join(cleaned.split())


def _d2core_affix_aliases(value: str, source_key: str) -> set[str]:
    aliases = {value, source_key}
    aliases.add(re.sub(r"\b\d+\b", "", value))
    aliases.add(value.removesuffix(" at level"))
    aliases.add(value.replace("Wild Lighting", "Wild Lightning"))
    aliases.add(value.replace(" Second After ", " Seconds After "))
    return {" ".join(alias.split()) for alias in aliases}


def _aspect_name_aliases(value: str) -> set[str]:
    aliases = {value}
    if value.startswith("Aspect "):
        aliases.add(value.removeprefix("Aspect "))
    if value.startswith("Aspect of the "):
        aliases.add(value.removeprefix("Aspect of the "))
    if value.startswith("Aspect of "):
        aliases.add(value.removeprefix("Aspect of "))
    if value.endswith(" Aspect"):
        aliases.add(value.removesuffix(" Aspect"))
    return aliases


def _d2core_translation_indexes(
    snapshot: d2core_data.D2CoreSnapshot,
) -> dict[str, dict[str, set[_TranslationCandidate]]]:
    indexes: dict[str, dict[str, set[_TranslationCandidate]]] = {
        "affix": defaultdict(set),
        "aspect": defaultdict(set),
        "charm_affix": defaultdict(set),
        "seal_affix": defaultdict(set),
        "set": defaultdict(set),
        "unique": defaultdict(set),
    }
    content_fields = {"affix": "descTpl", "aspect": "name", "uniqueItem": "name", "talisman": "text"}
    for dataset in content_fields:
        for english, chinese, multiplicity in _paired_d2core_records(snapshot, dataset):
            field = content_fields[dataset]
            english_text = cast("str", english[field])
            chinese_text = cast("str", chinese[field])
            if dataset == "talisman":
                section = cast("str", english["section"])
                if section == "itemSets":
                    kind = "set"
                    aliases = {english_text, cast("str", english["sourceKey"])}
                elif section in {"affixes.charm", "affixes.seal"}:
                    kind = "charm_affix" if section.endswith("charm") else "seal_affix"
                    english_text = _clean_d2core_affix(english_text)
                    chinese_text = _clean_d2core_affix(chinese_text)
                    aliases = _d2core_affix_aliases(english_text, cast("str", english["sourceKey"]))
                elif section == "seal":
                    kind = "unique"
                    aliases = {english_text}
                else:
                    continue
            elif dataset == "affix":
                kind = "affix"
                english_text = _clean_d2core_affix(english_text)
                chinese_text = _clean_d2core_affix(chinese_text)
                aliases = _d2core_affix_aliases(english_text, cast("str", english["key"]))
                multiplier_alias = ""
                if english_text.casefold().startswith("x "):
                    multiplier_alias = english_text[2:].strip()
                elif english_text.casefold().endswith(" x"):
                    multiplier_alias = english_text[:-2].strip()
                if multiplier_alias:
                    aliases.add(
                        multiplier_alias
                        if multiplier_alias.casefold().endswith(" multiplier")
                        else f"{multiplier_alias} multiplier"
                    )
            elif dataset == "aspect":
                kind = "aspect"
                aliases = _aspect_name_aliases(english_text)
                # Chinese legendary item names retain the possessive "之" but omit the class word "威能".
                chinese_text = chinese_text.removesuffix("威能").strip()
            else:
                kind = "unique"
                aliases = {english_text}

            if not english_text or not chinese_text:
                continue
            source_key = english.get("sourceKey", english["key"])
            source_id = f"{dataset}:{source_key}:{english['id']}:x{multiplicity}"
            source_record_sha256 = _canonical_record_hash({
                "dataset": dataset,
                "key": source_key,
                "id": english["id"],
                "multiplicity": multiplicity,
                "enUS": english_text,
                "zhCN": chinese_text,
            })
            candidate = _TranslationCandidate(
                text=chinese_text, provider="d2core", source_id=source_id, source_record_sha256=source_record_sha256
            )
            for alias in aliases:
                for identity in _index_identities(alias):
                    indexes[kind][identity].add(candidate)
    return indexes


def _d2core_translation_record_index(
    indexes: Mapping[str, Mapping[str, set[_TranslationCandidate]]],
) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for index in indexes.values():
        for candidates in index.values():
            for candidate in candidates:
                metadata = {
                    "source_record_sha256": candidate.source_record_sha256,
                    "translation_sha256": _sha256_text(candidate.text),
                }
                existing = records.get(candidate.source_id)
                if existing is not None and existing != metadata:
                    raise GenerationError(f"D2Core source ID has conflicting derived hashes: {candidate.source_id}")
                records[candidate.source_id] = metadata
    return dict(sorted(records.items()))


def _overlay_preferred_indexes(
    *indexes: Mapping[str, set[_TranslationCandidate]] | None,
) -> dict[str, set[_TranslationCandidate]]:
    """Overlay increasingly namespace-specific candidate indexes."""
    merged: dict[str, set[_TranslationCandidate]] = defaultdict(set)
    for index in indexes:
        if index is None:
            continue
        for identity, candidates in index.items():
            merged[identity] = set(candidates)
    return merged


def _preferred_candidate_values(
    index: Mapping[str, set[_TranslationCandidate]] | None, canonical: str, source_text: str
) -> set[_TranslationCandidate]:
    if index is None:
        return set()
    candidates: set[_TranslationCandidate] = set()
    for value in (canonical, canonical.replace("_", " "), source_text):
        candidates.update(index.get(_exact_index_identity(value), set()))
    if not candidates:
        for value in (canonical, canonical.replace("_", " "), source_text):
            candidates.update(index.get(_template_index_identity(value), set()))
        candidates = {
            _TranslationCandidate(
                text=_numeric_template_text(candidate.text),
                provider=candidate.provider,
                source_id=candidate.source_id,
                source_record_sha256=candidate.source_record_sha256,
            )
            for candidate in candidates
        }
    if "percent" not in canonical.casefold():
        non_percent = {candidate for candidate in candidates if "percent" not in candidate.source_id.casefold()}
        if non_percent:
            candidates = non_percent
    return candidates


def _source_record(stable_id: str, text: str) -> dict[str, str]:
    return {"stable_id": stable_id, "text": text, "source_sha256": _sha256_text(text)}


class _BundleBuilder:
    def __init__(self, reviewed_overrides: Mapping[str, str] | None = None) -> None:
        self.source_records: dict[str, dict[str, str]] = {}
        self.locale_records: dict[str, dict[str, object]] = {}
        self.unresolved: list[dict[str, str]] = []
        self.excluded_historical: list[dict[str, object]] = []
        self.translation_conflicts: list[dict[str, str]] = []
        self.translation_sources: Counter[str] = Counter()
        self.reviewed_overrides = dict(reviewed_overrides or {})
        self.used_overrides: set[str] = set()

    def resolve(
        self,
        stable_id: str,
        source_text: str,
        candidates: Iterable[str],
        *,
        preferred_candidates: Iterable[_TranslationCandidate] = (),
        fallback_provider: str = "diablo4_companion",
    ) -> str | None:
        if stable_id in self.source_records:
            raise GenerationError(f"duplicate stable ID while generating zhCN assets: {stable_id}")
        source_record = _source_record(stable_id, source_text)
        self.source_records[stable_id] = source_record
        preferred = set(preferred_candidates)
        fallback = set(candidates)
        translation = self.reviewed_overrides.get(stable_id)
        reason = None
        translation_source: dict[str, str] | None = None
        if translation is not None:
            self.used_overrides.add(stable_id)
            translation_source = {
                "provider": "reviewed_override",
                "source_id": stable_id,
                "translation_sha256": _sha256_text(translation),
            }
        else:
            fallback_translation, fallback_reason = _select_translation(fallback)
            preferred_translation, preferred_reason = _select_translation(candidate.text for candidate in preferred)
            translation = fallback_translation or preferred_translation
            reason = fallback_reason if not preferred_translation else preferred_reason
            if (
                fallback_translation is not None
                and preferred_translation is not None
                and _template_identity(fallback_translation) != _template_identity(preferred_translation)
            ):
                self.translation_conflicts.append({
                    "stable_id": stable_id,
                    "selected": fallback_translation,
                    "fallback": preferred_translation,
                    "selected_provider": fallback_provider,
                    "fallback_provider": "d2core",
                })
            if fallback_translation is not None:
                translation_source = {
                    "provider": fallback_provider,
                    "source_id": stable_id,
                    "translation_sha256": _sha256_text(fallback_translation),
                }
            elif preferred_translation is not None:
                matching_sources = sorted(
                    (candidate for candidate in preferred if candidate.text == preferred_translation),
                    key=lambda candidate: (candidate.source_id, candidate.source_record_sha256),
                )
                translation_source = matching_sources[0].source_record()
        if translation is None:
            self.unresolved.append({"stable_id": stable_id, "source_text": source_text, "reason": cast("str", reason)})
            return None
        if translation_source is None:
            raise GenerationError(f"resolved translation has no source metadata: {stable_id}")
        self.locale_records[stable_id] = {
            "stable_id": stable_id,
            "text": translation,
            "source_sha256": source_record["source_sha256"],
            "translation_source": translation_source,
        }
        self.translation_sources[translation_source["provider"]] += 1
        return translation

    def validate_overrides(self) -> None:
        unused = sorted(set(self.reviewed_overrides) - self.used_overrides)
        if unused:
            raise GenerationError(f"reviewed overrides contain unknown stable IDs: {', '.join(unused)}")


def _candidate_values(index: Mapping[str, set[str]], canonical: str, source_text: str) -> set[str]:
    candidates: set[str] = set()
    for value in (canonical, canonical.replace("_", " "), source_text):
        candidates.update(index.get(_exact_index_identity(value), set()))
    if not candidates:
        for value in (canonical, canonical.replace("_", " "), source_text):
            candidates.update(index.get(_template_index_identity(value), set()))
        candidates = {_numeric_template_text(candidate) for candidate in candidates}
    return candidates


def _simple_mapping(
    *,
    builder: _BundleBuilder,
    prefix: str,
    source: Mapping[str, object],
    index: Mapping[str, set[str]],
    preferred_index: Mapping[str, set[_TranslationCandidate]] | None = None,
) -> dict[str, str]:
    output: dict[str, str] = {}
    for canonical, raw_source_text in sorted(source.items()):
        if not isinstance(raw_source_text, str):
            raise GenerationError(f"{prefix}.json value for {canonical!r} must be a string")
        stable_id = f"{prefix}:{canonical}"
        translation = builder.resolve(
            stable_id,
            raw_source_text,
            _candidate_values(index, canonical, raw_source_text),
            preferred_candidates=_preferred_candidate_values(preferred_index, canonical, raw_source_text),
        )
        output[canonical] = translation or ""
    return output


def _item_type_mapping(
    builder: _BundleBuilder, source: Mapping[str, object], index: Mapping[str, set[str]]
) -> dict[str, str]:
    output: dict[str, str] = {}
    for canonical, raw_source_text in sorted(source.items()):
        if not isinstance(raw_source_text, str):
            raise GenerationError(f"item_types.json value for {canonical!r} must be a string")
        if canonical in _NON_FILTERABLE_ITEM_TYPES:
            output[canonical] = ""
            continue
        translation = builder.resolve(
            f"item_types:{canonical}", raw_source_text, _candidate_values(index, canonical, raw_source_text)
        )
        output[canonical] = translation or ""
    return output


def _aspect_mapping(
    builder: _BundleBuilder,
    source: Sequence[object],
    index: Mapping[str, set[str]],
    preferred_index: Mapping[str, set[_TranslationCandidate]] | None = None,
) -> dict[str, str]:
    output: dict[str, str] = {}
    for canonical in sorted({value for value in source if isinstance(value, str)}):
        source_text = canonical.replace("_", " ")
        translation = builder.resolve(
            f"aspects:{canonical}",
            source_text,
            _candidate_values(index, canonical, source_text),
            preferred_candidates=_preferred_candidate_values(preferred_index, canonical, source_text),
        )
        output[canonical] = translation or ""
    if len(output) != len(set(source)):
        raise GenerationError("enUS aspects.json must contain only strings")
    return output


def _set_mapping(
    builder: _BundleBuilder,
    source: Sequence[object],
    preferred_index: Mapping[str, set[_TranslationCandidate]] | None = None,
) -> dict[str, str]:
    output: dict[str, str] = {}
    for canonical in sorted({value for value in source if isinstance(value, str)}):
        source_text = canonical.replace("_", " ")
        translation = builder.resolve(
            f"sets:{canonical}",
            source_text,
            (),
            preferred_candidates=_preferred_candidate_values(preferred_index, canonical, source_text),
        )
        output[canonical] = translation or ""
    if len(output) != len(set(source)):
        raise GenerationError("enUS sets.json must contain only strings")
    return output


def _unique_mapping(
    builder: _BundleBuilder,
    source: Mapping[str, object],
    index: Mapping[str, set[str]],
    preferred_index: Mapping[str, set[_TranslationCandidate]] | None = None,
) -> dict[str, object]:
    output: dict[str, object] = {}
    for canonical, metadata in sorted(source.items()):
        if not isinstance(metadata, dict):
            raise GenerationError(f"uniques.json value for {canonical!r} must be an object")
        source_text = canonical.replace("_", " ")
        translation = builder.resolve(
            f"uniques:{canonical}",
            source_text,
            _candidate_values(index, canonical, source_text),
            preferred_candidates=_preferred_candidate_values(preferred_index, canonical, source_text),
        )
        localized_metadata = dict(metadata)
        if translation is not None:
            localized_metadata["display_name"] = translation
        output[canonical] = localized_metadata
    return output


def _paired_rows(path_en: Path, path_zh: Path, label: str) -> list[tuple[dict[str, object], dict[str, object]]]:
    english = _json_array(path_en, f"enUS {label}")
    chinese = _json_array(path_zh, f"zhCN {label}")
    if len(english) != len(chinese):
        raise GenerationError(f"{label} enUS/zhCN record counts differ: {len(english)} != {len(chinese)}")
    pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    for index, (english_row, chinese_row) in enumerate(zip(english, chinese, strict=True)):
        if not isinstance(english_row, dict) or not isinstance(chinese_row, dict):
            raise GenerationError(f"{label}[{index}] must contain objects")
        pairs.append((cast("dict[str, object]", english_row), cast("dict[str, object]", chinese_row)))
    return pairs


def _strip_rarity(grammar: LocaleGrammar, text: str, source_rarity: str) -> str:
    rarity_name = _ITEM_RARITY_NAMES.get(source_rarity)
    return grammar.strip_rarity(text, rarity_name) if rarity_name else text.strip()


def _item_type_index(companion_repo: Path, en_grammar: LocaleGrammar, zh_grammar: LocaleGrammar) -> dict[str, set[str]]:
    data_dir = companion_repo / "D4Companion" / "Data"
    pairs = _paired_rows(data_dir / "ItemTypes.enUS.json", data_dir / "ItemTypes.zhCN.json", "ItemTypes")
    index: dict[str, set[str]] = defaultdict(set)
    for row_index, (english, chinese) in enumerate(pairs):
        for field in ("Name", "Rarerity", "Type"):
            if not isinstance(english.get(field), str) or not isinstance(chinese.get(field), str):
                raise GenerationError(f"ItemTypes[{row_index}].{field} must be a string")
        if (english["Rarerity"], english["Type"]) != (chinese["Rarerity"], chinese["Type"]):
            raise GenerationError(f"ItemTypes[{row_index}] enUS/zhCN identity fields differ")
        source_rarity = cast("str", english["Rarerity"])
        english_name = _strip_rarity(en_grammar, cast("str", english["Name"]), source_rarity)
        chinese_name = _strip_rarity(zh_grammar, cast("str", chinese["Name"]), source_rarity)
        index[_exact_index_identity(english_name)].add(chinese_name)
        if not source_rarity:
            index[_exact_index_identity(cast("str", english["Type"]))].add(chinese_name)
    return index


def _sigil_index(companion_repo: Path) -> dict[tuple[str, str], set[str]]:
    data_dir = companion_repo / "D4Companion" / "Data"
    pairs = _paired_rows(data_dir / "Sigils.enUS.json", data_dir / "Sigils.zhCN.json", "Sigils")
    chinese_by_identity: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for _, chinese in pairs:
        for field in ("IdName", "IdSno"):
            value = chinese.get(field)
            if isinstance(value, int | str):
                chinese_by_identity[field, str(value)].append(chinese)

    index: dict[tuple[str, str], set[str]] = defaultdict(set)
    english_rows = [english for english, _ in pairs]
    for row_index, english in enumerate(english_rows):
        source_type = english.get("Type")
        source_name = english.get("Name")
        if not isinstance(source_type, str) or not isinstance(source_name, str):
            raise GenerationError(f"Sigils[{row_index}] Type and Name must be strings")
        section = _SIGIL_SECTIONS.get(source_type)
        if section is None:
            continue
        matches: dict[str, dict[str, object]] = {}
        for field in ("IdName", "IdSno"):
            identity_value = english.get(field)
            if isinstance(identity_value, int | str):
                for match in chinese_by_identity.get((field, str(identity_value)), []):
                    matches[json.dumps(match, ensure_ascii=False, sort_keys=True)] = match
        for match in matches.values():
            chinese_name = match.get("Name")
            chinese_description = match.get("Description")
            if not isinstance(chinese_name, str) or not isinstance(chinese_description, str):
                continue
            display = chinese_name.strip()
            if section != "dungeons" and chinese_description.strip():
                display = f"{display} {chinese_description.strip()}"
            index[section, _identity(source_name)].add(display)
    return index


def _sigil_mapping(
    builder: _BundleBuilder, source: Mapping[str, object], index: Mapping[tuple[str, str], set[str]]
) -> dict[str, object]:
    output: dict[str, object] = {}
    for section in ("dungeons", "major", "minor", "positive"):
        raw_entries = source.get(section)
        if not isinstance(raw_entries, dict):
            raise GenerationError(f"sigils.json section {section!r} must be an object")
        localized: dict[str, str] = {}
        for canonical, raw_source_text in sorted(raw_entries.items()):
            if not isinstance(canonical, str) or not isinstance(raw_source_text, str):
                raise GenerationError(f"sigils.json section {section!r} must map strings to strings")
            translation = builder.resolve(
                f"sigils:{section}:{canonical}",
                raw_source_text,
                index.get((section, _identity(canonical.replace("_", " "))), set()),
            )
            localized[canonical] = translation or ""
        output[section] = localized
    rarities = source.get("rarities")
    if not isinstance(rarities, dict):
        raise GenerationError("sigils.json section 'rarities' must be an object")
    output["rarities"] = dict(rarities)
    return output


def _flat_mapping(builder: _BundleBuilder, prefix: str, source: Mapping[str, object]) -> dict[str, str]:
    output: dict[str, str] = {}
    for canonical, raw_source_text in sorted(source.items()):
        if not isinstance(raw_source_text, str):
            raise GenerationError(f"{prefix}.json must map strings to strings")
        output[canonical] = builder.resolve(f"{prefix}:{canonical}", raw_source_text, ()) or ""
    return output


def _runtime_tts_identity(value: str) -> str:
    letters_and_spaces = "".join(character for character in value if character.isalpha() or character.isspace())
    normalized = unicodedata.normalize("NFKC", letters_and_spaces).casefold()
    return " ".join(normalized.split())


def _selected_alias_collisions(namespaces: Mapping[str, Sequence[tuple[str, str]]]) -> list[dict[str, object]]:
    collisions: list[dict[str, object]] = []
    for namespace, entries in namespaces.items():
        grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"stable_ids": set(), "texts": set()})
        for stable_id, text in entries:
            for identity in dict.fromkeys((_identity(text), _runtime_tts_identity(text))):
                if not identity:
                    continue
                grouped[identity]["stable_ids"].add(stable_id)
                grouped[identity]["texts"].add(text)
        for identity, values in sorted(grouped.items()):
            if len(values["stable_ids"]) > 1:
                collisions.append({
                    "namespace": namespace,
                    "normalized_alias": identity,
                    "stable_ids": sorted(values["stable_ids"]),
                    "texts": sorted(values["texts"]),
                })
    return collisions


def _partition_disambiguated_alias_collisions(
    collisions: Sequence[dict[str, object]], grammar: LocaleGrammar
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    unresolved: list[dict[str, object]] = []
    disambiguated: list[dict[str, object]] = []
    for collision in collisions:
        texts = collision.get("texts")
        stable_ids = collision.get("stable_ids")
        if not isinstance(texts, list) or len(texts) != 1:
            unresolved.append(collision)
            continue
        if not isinstance(stable_ids, list) or not all(isinstance(value, str) for value in stable_ids):
            unresolved.append(collision)
            continue
        display_text = texts[0]
        if not isinstance(display_text, str):
            unresolved.append(collision)
            continue
        if collision.get("namespace") == "aspects":
            canonical_ids = grammar.equivalent_aspects(display_text)
            if set(canonical_ids) != set(stable_ids):
                unresolved.append(collision)
                continue
            disambiguated.append({
                **collision,
                "strategy": "equivalent_canonical_ids",
                "canonical_ids": sorted(canonical_ids),
            })
            continue
        if collision.get("namespace") != "affixes":
            unresolved.append(collision)
            continue
        mapping = {
            precision: grammar.affix_for_range_precision(display_text, precision)
            for precision in ("decimal", "integer")
        }
        if None in mapping.values() or set(mapping.values()) != set(stable_ids):
            unresolved.append(collision)
            continue
        disambiguated.append({**collision, "strategy": "range_precision", "mapping": mapping})
    return unresolved, disambiguated


def _grammar(path: Path, locale: str) -> tuple[dict[str, object], LocaleGrammar]:
    data = _json_object(path, f"{locale} grammar")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise GenerationError(f"{locale} grammar schema_version must equal {SCHEMA_VERSION}")
    return data, LocaleGrammar.from_dict(locale, data)


def _reviewed_overrides(path: Path) -> tuple[dict[str, str], str]:
    data = _json_object(path, "reviewed zhCN overrides")
    if data.get("schema_version") != SCHEMA_VERSION or data.get("locale") != "zhCN":
        raise GenerationError("reviewed zhCN overrides must use schema version 1 and locale zhCN")
    if "evidence" in data:
        raise GenerationError("reviewed zhCN overrides must not contain private capture evidence")
    raw_records = data.get("records")
    if not isinstance(raw_records, dict):
        raise GenerationError("reviewed zhCN overrides records must be an object")

    records: dict[str, str] = {}
    for stable_id, text in raw_records.items():
        if not isinstance(stable_id, str) or not stable_id.strip() or not isinstance(text, str) or not text.strip():
            raise GenerationError("reviewed zhCN overrides must map non-empty stable IDs to non-empty strings")
        if _is_ascii_placeholder(text):
            raise GenerationError(f"reviewed zhCN override {stable_id!r} is an ASCII placeholder")
        records[stable_id] = text
    return records, _sha256_text(_canonical_json_text(data))


def _augment_source_files(sources: dict[str, object], companion_repo: Path) -> None:
    companion = sources.get("diablo4_companion")
    if not isinstance(companion, dict):
        raise GenerationError("Companion source metadata is missing")
    companion_metadata = cast("dict[str, object]", companion)
    files = companion_metadata.get("files")
    if not isinstance(files, dict):
        raise GenerationError("Companion source file metadata is missing")
    source_files = cast("dict[str, object]", files)
    for filename in ("ItemTypes.enUS.json", "ItemTypes.zhCN.json", "Sigils.enUS.json", "Sigils.zhCN.json"):
        relative_path = f"D4Companion/Data/{filename}"
        path = companion_repo / relative_path
        payload = _load_json(path, relative_path)
        source_files[relative_path] = {
            "records": len(payload) if isinstance(payload, list) else 0,
            "sha256": companion_data.git_file_sha256(companion_repo, relative_path),
        }


def generate_zhcn_assets(
    *,
    companion_repo: Path,
    d4data_repo: Path,
    en_us_dir: Path,
    zhcn_grammar: Path,
    output_dir: Path,
    catalog_dir: Path,
    reviewed_overrides: Path | None = None,
    d2core_dir: Path | None = None,
) -> GeneratedBundle:
    en_grammar_data, en_grammar = _grammar(en_us_dir / "grammar.json", "enUS")
    del en_grammar_data
    zh_grammar_data, zh_grammar = _grammar(zhcn_grammar, "zhCN")

    source_records = companion_data.load_companion_records(companion_repo)
    entries, canonical_by_record = companion_data.join_records(source_records)
    sources = companion_data.collect_source_metadata(companion_repo, d4data_repo, source_records)
    _augment_source_files(sources, companion_repo)
    companion_quality = companion_data.build_quality_report(source_records, entries, canonical_by_record)

    d4data_source = sources.get("d4data")
    d4data_build = d4data_source.get("build") if isinstance(d4data_source, dict) else None
    if not isinstance(d4data_build, str):
        raise GenerationError("d4data source metadata has no game build")
    build_version = d4data_build

    d2core_indexes: dict[str, dict[str, set[_TranslationCandidate]]] = {}
    d2core_translation_records: dict[str, dict[str, str]] = {}
    d2core_build_version: str | None = None
    if d2core_dir is not None:
        try:
            d2core_snapshot = d2core_data.load_snapshot(d2core_dir)
        except d2core_data.D2CoreDataError as exc:
            raise GenerationError(f"invalid D2Core snapshot: {exc}") from exc
        d2core_indexes = _d2core_translation_indexes(d2core_snapshot)
        d2core_translation_records = _d2core_translation_record_index(d2core_indexes)
        d2core_build_version = d2core_snapshot.build_version
        sources["d2core"] = {
            **dict(d2core_snapshot.manifest),
            "snapshot_manifest_sha256": _sha256_file(d2core_snapshot.manifest_path),
            "translation_record_index": d2core_translation_records,
        }

    d4data_build_id = build_version.rsplit(".", maxsplit=1)[-1]
    source_builds_match = d2core_build_version is None or d2core_build_version == d4data_build_id

    override_records: dict[str, str] = {}
    override_metadata: dict[str, str] | None = None
    if reviewed_overrides is not None:
        override_records, override_sha256 = _reviewed_overrides(reviewed_overrides)
        override_metadata = {"path": reviewed_overrides.name, "sha256": override_sha256}

    builder = _BundleBuilder(override_records)
    affix_index = _translation_index(entries, "affix")
    aspect_index = _translation_index(entries, "aspect")
    unique_index = _translation_index(entries, "unique")
    item_type_index = _item_type_index(companion_repo, en_grammar, zh_grammar)
    sigil_index = _sigil_index(companion_repo)
    charm_preferred_index = _overlay_preferred_indexes(d2core_indexes.get("affix"), d2core_indexes.get("charm_affix"))
    seal_preferred_index = _overlay_preferred_indexes(d2core_indexes.get("affix"), d2core_indexes.get("seal_affix"))
    unique_preferred_index = _overlay_preferred_indexes(d2core_indexes.get("unique"))

    affixes = _simple_mapping(
        builder=builder,
        prefix="affixes",
        source=_json_object(en_us_dir / "affixes.json", "enUS affixes"),
        index=affix_index,
        preferred_index=d2core_indexes.get("affix"),
    )
    charm_affixes = _simple_mapping(
        builder=builder,
        prefix="charms_affixes",
        source=_json_object(en_us_dir / "charms_affixes.json", "enUS charm affixes"),
        index=affix_index,
        preferred_index=charm_preferred_index,
    )
    seal_affixes = _simple_mapping(
        builder=builder,
        prefix="seals_affixes",
        source=_json_object(en_us_dir / "seals_affixes.json", "enUS seal affixes"),
        index=affix_index,
        preferred_index=seal_preferred_index,
    )
    aspects = _aspect_mapping(
        builder, _json_array(en_us_dir / "aspects.json", "enUS aspects"), aspect_index, d2core_indexes.get("aspect")
    )
    uniques = _unique_mapping(
        builder, _json_object(en_us_dir / "uniques.json", "enUS uniques"), unique_index, unique_preferred_index
    )
    item_types_source = _json_object(en_us_dir / "item_types.json", "enUS item types")
    excluded_item_types = sorted(_NON_FILTERABLE_ITEM_TYPES.intersection(item_types_source))
    item_types = _item_type_mapping(builder, item_types_source, item_type_index)
    sigils = _sigil_mapping(builder, _json_object(en_us_dir / "sigils.json", "enUS sigils"), sigil_index)
    sets = _set_mapping(builder, _json_array(en_us_dir / "sets.json", "enUS sets"), d2core_indexes.get("set"))
    tributes = _flat_mapping(builder, "tributes", _json_object(en_us_dir / "tributes.json", "enUS tributes"))

    item_power_candidates = zh_grammar.terms("item_power")
    item_power_source = _json_object(en_us_dir / "tooltips.json", "enUS tooltips").get("ItemPower", "item power")
    if not isinstance(item_power_source, str):
        raise GenerationError("enUS tooltips ItemPower must be a string")
    item_power = builder.resolve(
        "tooltips:ItemPower", item_power_source, item_power_candidates, fallback_provider="locale_grammar"
    )
    tooltips = {"ItemPower": item_power} if item_power is not None else {}
    corrections = {"bad_tts_uniques": {}, "filter_after_keyword": [], "filter_words": []}
    builder.validate_overrides()

    runtime_payloads: dict[str, object] = {
        "affixes.json": affixes,
        "aspects.json": aspects,
        "charms_affixes.json": charm_affixes,
        "corrections.json": corrections,
        "grammar.json": zh_grammar_data,
        "item_types.json": item_types,
        "seals_affixes.json": seal_affixes,
        "sets.json": sets,
        "sigils.json": sigils,
        "tooltips.json": tooltips,
        "tributes.json": tributes,
        "uniques.json": uniques,
    }
    unique_aliases: list[tuple[str, str]] = []
    for canonical, metadata in uniques.items():
        display_name = metadata.get("display_name") if isinstance(metadata, dict) else None
        if isinstance(display_name, str) and f"uniques:{canonical}" in builder.source_records:
            unique_aliases.append((canonical, display_name))
    sigil_aliases = [
        (canonical, text)
        for section, values in sigils.items()
        if section != "rarities" and isinstance(values, dict)
        for canonical, text in values.items()
        if isinstance(canonical, str)
        and isinstance(text, str)
        and f"sigils:{section}:{canonical}" in builder.source_records
    ]
    selected_alias_collisions = _selected_alias_collisions({
        "affixes": [
            *(
                (canonical, text)
                for canonical, text in affixes.items()
                if f"affixes:{canonical}" in builder.source_records
            ),
            *(
                (canonical, text)
                for canonical, text in charm_affixes.items()
                if f"charms_affixes:{canonical}" in builder.source_records
            ),
            *(
                (canonical, text)
                for canonical, text in seal_affixes.items()
                if f"seals_affixes:{canonical}" in builder.source_records
            ),
        ],
        "aspects": [
            (canonical, text) for canonical, text in aspects.items() if f"aspects:{canonical}" in builder.source_records
        ],
        "item_types": [
            (canonical, text)
            for canonical, text in item_types.items()
            if f"item_types:{canonical}" in builder.source_records
        ],
        "sets": [
            (canonical, text) for canonical, text in sets.items() if f"sets:{canonical}" in builder.source_records
        ],
        "sigils": sigil_aliases,
        "tributes": [
            (canonical, text)
            for canonical, text in tributes.items()
            if f"tributes:{canonical}" in builder.source_records
        ],
        "uniques": unique_aliases,
    })
    selected_alias_collisions, disambiguated_alias_collisions = _partition_disambiguated_alias_collisions(
        selected_alias_collisions, zh_grammar
    )
    selected_quality = {
        "ok": not selected_alias_collisions,
        "alias_collisions": selected_alias_collisions,
        "disambiguated_alias_collisions": disambiguated_alias_collisions,
    }
    source_quality_ok = selected_quality["ok"]
    for filename, payload in runtime_payloads.items():
        _write_json(output_dir / filename, payload)

    source_manifest_path = catalog_dir / "source-manifest.json"
    source_manifest = {
        "schema_version": SCHEMA_VERSION,
        "build_version": build_version,
        "source_locale": "enUS",
        "sources": sources,
        "records": [builder.source_records[key] for key in sorted(builder.source_records)],
    }
    _write_json(source_manifest_path, source_manifest)
    source_manifest_sha256 = _sha256_file(source_manifest_path)

    build_version_path = catalog_dir / "d4data-buildVersion.txt"
    build_version_path.parent.mkdir(parents=True, exist_ok=True)
    build_version_path.write_text(build_version + "\n", encoding="utf-8", newline="\n")
    source_lock_path = catalog_dir / "source-lock.json"
    _write_json(
        source_lock_path,
        {
            "schema_version": SCHEMA_VERSION,
            "build_version": build_version,
            "source_manifest": {"path": source_manifest_path.name, "sha256": source_manifest_sha256},
        },
    )

    runtime_ready = (
        not builder.unresolved and not builder.translation_conflicts and source_quality_ok and source_builds_match
    )
    locale_manifest_path = output_dir / "manifest.json"
    locale_manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "build_version": build_version,
        "locale": "zhCN",
        "runtime_ready": runtime_ready,
        "source_quality_ok": source_quality_ok,
        "translation_conflicts": len(builder.translation_conflicts),
        "source_manifest_sha256": source_manifest_sha256,
        "files": [{"path": filename, "sha256": _sha256_file(output_dir / filename)} for filename in RUNTIME_FILES],
        "records": [builder.locale_records[key] for key in sorted(builder.locale_records)],
    }
    if override_metadata is not None:
        locale_manifest["reviewed_overrides"] = override_metadata
    _write_json(locale_manifest_path, locale_manifest)

    unresolved_counts = Counter(issue["stable_id"].split(":", maxsplit=1)[0] for issue in builder.unresolved)
    extension_unresolved = sum(unresolved_counts[kind] for kind in ("sigils", "tributes"))
    equipment_unresolved = len(builder.unresolved) - extension_unresolved
    quality_report_path = output_dir / "quality-report.json"
    _write_json(
        quality_report_path,
        {
            "schema_version": SCHEMA_VERSION,
            "build_version": build_version,
            "locale": "zhCN",
            "runtime_ready": runtime_ready,
            "scope": {
                "excluded_item_types": excluded_item_types,
                "reason": "D4LF ignores these non-gear item types before profile filtering.",
                "excluded_historical_records": sorted(builder.excluded_historical, key=itemgetter("stable_id")),
                "historical_reason": (
                    "No translation provider is authoritative by absence. D2Core may supplement missing translations, "
                    "but records are never excluded merely because D2Core does not contain them."
                ),
            },
            "summary": {
                "source_records": len(builder.source_records),
                "resolved_records": len(builder.locale_records),
                "unresolved_records": len(builder.unresolved),
                "excluded_records": len(excluded_item_types) + len(builder.excluded_historical),
                "excluded_historical_records": len(builder.excluded_historical),
                "equipment_unresolved_records": equipment_unresolved,
                "extension_unresolved_records": extension_unresolved,
                "reviewed_overrides": len(builder.used_overrides),
                "translation_conflicts": len(builder.translation_conflicts),
                "translation_sources": dict(sorted(builder.translation_sources.items())),
                "unresolved_by_kind": dict(sorted(unresolved_counts.items())),
                "source_quality_ok": source_quality_ok,
                "source_builds_match": source_builds_match,
            },
            "source_builds": {"d4data": build_version, "d2core": d2core_build_version},
            "translation_conflicts": sorted(builder.translation_conflicts, key=itemgetter("stable_id")),
            "unresolved": sorted(builder.unresolved, key=itemgetter("stable_id")),
            "selected_quality": selected_quality,
            "companion_quality": companion_quality,
        },
    )
    return GeneratedBundle(
        output_dir=output_dir,
        catalog_dir=catalog_dir,
        quality_report=quality_report_path,
        locale_manifest=locale_manifest_path,
        source_lock=source_lock_path,
        runtime_ready=runtime_ready,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate stable-key zhCN candidate assets from public data sources.")
    parser.add_argument("--companion-repo", required=True, type=Path)
    parser.add_argument("--d4data-repo", required=True, type=Path)
    parser.add_argument("--en-us-dir", required=True, type=Path)
    parser.add_argument("--zhcn-grammar", required=True, type=Path)
    parser.add_argument(
        "--d2core-dir",
        type=Path,
        help=(
            "Optional validated D2Core snapshot directory; supplements missing Companion translations "
            "without excluding records by provider absence."
        ),
    )
    parser.add_argument(
        "--reviewed-overrides",
        type=Path,
        help="Optional publishable zhCN stable-ID translations with no private capture evidence.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--catalog-dir", required=True, type=Path)
    parser.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="Return success for diagnostic candidate output even when the release gate remains closed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        bundle = generate_zhcn_assets(
            companion_repo=arguments.companion_repo,
            d4data_repo=arguments.d4data_repo,
            en_us_dir=arguments.en_us_dir,
            zhcn_grammar=arguments.zhcn_grammar,
            output_dir=arguments.output_dir,
            catalog_dir=arguments.catalog_dir,
            reviewed_overrides=arguments.reviewed_overrides,
            d2core_dir=arguments.d2core_dir,
        )
    except (GenerationError, companion_data.CompanionDataError, d2core_data.D2CoreDataError, OSError) as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        return 2
    print(bundle.quality_report)
    if bundle.runtime_ready or arguments.allow_unresolved:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
