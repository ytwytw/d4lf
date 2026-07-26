import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def normalize_locale_text(value: str) -> str:
    """Normalize display text without removing CJK characters."""
    value = unicodedata.normalize("NFKC", value).replace("\xa0", " ")
    return " ".join(value.casefold().split())


def canonical_text_key(value: str) -> str:
    """Create a backwards-compatible profile key from localized display text."""
    value = normalize_locale_text(value)
    value = re.sub(r"[\s,()]+", "_", value)
    value = value.replace("'", "")
    return value.strip("_")


def _string_list(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        values: tuple[str, ...] = (value,)
    elif isinstance(value, list):
        string_values: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return ()
            string_values.append(item)
        values = tuple(string_values)
    else:
        return ()
    return tuple(item for item in values if normalize_locale_text(item))


def _term_map(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    return {key: _string_list(terms) for key, terms in value.items() if isinstance(key, str)}


def _normalized_term_map(value: object) -> dict[str, tuple[str, ...]]:
    return {
        normalized: terms
        for key, terms in _term_map(value).items()
        if (normalized := normalize_locale_text(key)) and terms
    }


def _nested_string_map(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for display_text, raw_mapping in value.items():
        if not isinstance(display_text, str) or not isinstance(raw_mapping, dict):
            continue
        mapping = {
            key: canonical
            for key, canonical in raw_mapping.items()
            if isinstance(key, str) and isinstance(canonical, str) and canonical
        }
        normalized = normalize_locale_text(display_text)
        if normalized and mapping:
            result[normalized] = mapping
    return result


@dataclass(frozen=True)
class LocaleGrammar:
    locale: str
    labels: dict[str, tuple[str, ...]] = field(default_factory=dict)
    identifiers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    rarities: dict[str, tuple[str, ...]] = field(default_factory=dict)
    affix_range_precision: dict[str, dict[str, str]] = field(default_factory=dict)
    aspect_alias_equivalence: dict[str, tuple[str, ...]] = field(default_factory=dict)
    schema_version: int = 1

    @classmethod
    def from_dict(cls, locale: str, data: Mapping[str, object]) -> LocaleGrammar:
        raw_schema_version = data.get("schema_version", 1)
        schema_version = int(raw_schema_version) if isinstance(raw_schema_version, int | str) else 1
        return cls(
            locale=locale,
            schema_version=schema_version,
            labels=_term_map(data.get("labels")),
            identifiers=_term_map(data.get("identifiers")),
            rarities=_term_map(data.get("rarities")),
            affix_range_precision=_nested_string_map(data.get("affix_range_precision")),
            aspect_alias_equivalence=_normalized_term_map(data.get("aspect_alias_equivalence")),
        )

    def terms(self, key: str) -> tuple[str, ...]:
        return self.labels.get(key, ())

    def identifier_terms(self, key: str) -> tuple[str, ...]:
        return self.identifiers.get(key, ())

    def contains(self, key: str, value: str) -> bool:
        normalized = normalize_locale_text(value)
        return any(normalize_locale_text(term) in normalized for term in self.terms(key))

    def equals(self, key: str, value: str) -> bool:
        normalized = normalize_locale_text(value)
        return any(normalized == normalize_locale_text(term) for term in self.terms(key))

    def startswith(self, key: str, value: str) -> bool:
        normalized = normalize_locale_text(value)
        return any(normalized.startswith(normalize_locale_text(term)) for term in self.terms(key))

    def endswith(self, key: str, value: str) -> bool:
        normalized = normalize_locale_text(value)
        return any(normalized.endswith(normalize_locale_text(term)) for term in self.terms(key))

    def strip_terms(self, value: str, *keys: str) -> str:
        result = normalize_locale_text(value)
        for key in keys:
            for term in self.terms(key):
                result = result.replace(normalize_locale_text(term), " ")
        return " ".join(result.split())

    def rarity_name(self, value: str) -> str | None:
        normalized = normalize_locale_text(value)
        matches: list[tuple[int, str]] = []
        for member_name, aliases in self.rarities.items():
            for alias in aliases:
                normalized_alias = normalize_locale_text(alias)
                if normalized.startswith(normalized_alias):
                    matches.append((len(normalized_alias), member_name))
        return max(matches, default=(0, None))[1]

    def strip_rarity(self, value: str, member_name: str | None = None) -> str:
        result = normalize_locale_text(value)
        items = self.rarities.items() if member_name is None else ((member_name, self.rarities.get(member_name, ())),)
        for _, aliases in items:
            for alias in sorted(aliases, key=len, reverse=True):
                result = result.replace(normalize_locale_text(alias), " ")
        return " ".join(result.split())

    def identifier_matches(self, key: str, value: str, *, mode: str = "contains") -> bool:
        normalized = normalize_locale_text(value)
        for term in self.identifier_terms(key):
            normalized_term = normalize_locale_text(term)
            if mode == "startswith" and normalized.startswith(normalized_term):
                return True
            if mode == "endswith" and normalized.endswith(normalized_term):
                return True
            if mode == "contains" and normalized_term in normalized:
                return True
        return False

    def affix_for_range_precision(self, display_text: str, precision: str | None) -> str | None:
        if precision not in {"decimal", "integer"}:
            return None
        mapping = self.affix_range_precision.get(normalize_locale_text(display_text), {})
        return mapping.get(precision)

    def equivalent_aspects(self, display_text: str) -> tuple[str, ...]:
        return self.aspect_alias_equivalence.get(normalize_locale_text(display_text), ())
