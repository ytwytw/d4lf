import json
import logging
import pathlib
import threading
from typing import ClassVar, Self

import rapidfuzz

from src.game_data.item_type import ItemType
from src.game_data.localized_maps import (
    load_localized_display_map,
    load_localized_metadata_map,
    load_localized_nested_string_map,
    load_localized_string_map,
)
from src.locale_data import LocaleGrammar, normalize_locale_text
from src.settings import BASE_DIR, get_settings

LOGGER = logging.getLogger(__name__)
GAME_CATALOG_LOCK = threading.RLock()


class GameCatalog:
    """Localized Diablo 4 reference data shared by the Item and Profiles capabilities."""

    affix_dict: dict[str, str] = {}
    charm_affix_dict: dict[str, str] = {}
    seal_affix_dict: dict[str, str] = {}
    affix_sigil_dict: dict[str, str] = {}
    affix_sigil_dict_all: dict[str, dict[str, str]] = {}
    aspect_list: list[str] = []
    aspect_dict: dict[str, str] = {}
    aspect_unique_dict: dict[str, dict[str, object]] = {}
    bad_tts_uniques: dict[str, str] = {}
    filter_after_keyword: list[str] = []
    filter_words: list[str] = []
    item_types_dict: dict[str, str] = {}
    set_list: list[str] = []
    set_dict: dict[str, str] = {}
    tooltips: dict[str, str] = {}
    tribute_dict: dict[str, str] = {}
    grammar = LocaleGrammar(locale="enUS")

    _instance: ClassVar[Self | None] = None
    data_loaded = False

    def __new__(cls) -> Self:
        with GAME_CATALOG_LOCK:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance.data_loaded = False
                cls._instance = instance
                try:
                    instance.load_data()
                except BaseException:
                    cls._instance = None
                    instance.data_loaded = False
                    raise
                instance.data_loaded = True
            return cls._instance

    def load_data(self) -> None:
        language = str(get_settings().general.language)
        language_dir = pathlib.Path(BASE_DIR / f"assets/lang/{language}")
        self.affix_dict = load_localized_string_map(language_dir, "affixes.json")
        self.seal_affix_dict = load_localized_string_map(language_dir, "seals_affixes.json")
        self.charm_affix_dict = load_localized_string_map(language_dir, "charms_affixes.json")
        self.aspect_dict = load_localized_display_map(language_dir, "aspects.json")
        self.aspect_list = list(self.aspect_dict)

        with (language_dir / "corrections.json").open(encoding="utf-8") as file:
            corrections = json.load(file)
        self.filter_after_keyword = corrections["filter_after_keyword"]
        self.filter_words = corrections["filter_words"]
        self.bad_tts_uniques = corrections["bad_tts_uniques"]

        self.item_types_dict = load_localized_string_map(language_dir, "item_types.json")
        for item in self.item_types_dict:
            if item not in ItemType.__members__:
                LOGGER.warning("%s type not in item_type.py", item)

        self.affix_sigil_dict_all = load_localized_nested_string_map(language_dir, "sigils.json")
        self.affix_sigil_dict = {
            key: value
            for section in ("dungeons", "minor", "major", "positive")
            for key, value in self.affix_sigil_dict_all[section].items()
        }
        self.tribute_dict = load_localized_string_map(language_dir, "tributes.json")
        self.tooltips = load_localized_string_map(language_dir, "tooltips.json")
        self.aspect_unique_dict = load_localized_metadata_map(language_dir, "uniques.json")
        self.set_dict = load_localized_display_map(language_dir, "sets.json")
        self.set_list = list(self.set_dict)

        grammar_path = language_dir / "grammar.json"
        if grammar_path.exists():
            with grammar_path.open(encoding="utf-8") as file:
                self.grammar = LocaleGrammar.from_dict(language, json.load(file))
        else:
            LOGGER.warning("No grammar data found for %s; localized TTS parsing is unavailable", language)
            self.grammar = LocaleGrammar(locale=language)

        self._affix_aliases = self._alias_index(self.affix_dict)
        self._charm_affix_aliases = self._alias_index(self.charm_affix_dict)
        self._seal_affix_aliases = self._alias_index(self.seal_affix_dict)
        self._aspect_aliases = self._alias_index(self.aspect_dict)
        self._item_type_aliases = self._item_type_alias_index(self.item_types_dict)
        self._set_aliases = self._alias_index(self.set_dict)
        self._sigil_aliases = {
            section: self._alias_index(self.affix_sigil_dict_all[section])
            for section in ("dungeons", "major", "minor", "positive")
        }
        self._tribute_aliases = self._alias_index(self.tribute_dict)
        self._unique_aliases = self._unique_alias_index(self.aspect_unique_dict)

    def item_type_label(self, item_type: ItemType) -> str:
        return self.item_types_dict.get(item_type.name, item_type.value)

    def item_type_names(self, item_type: ItemType) -> tuple[str, ...]:
        return tuple(dict.fromkeys((item_type.name, item_type.value, self.item_type_label(item_type))))

    def item_type_from_text(self, value: str) -> ItemType | None:
        resolved = self.resolve_item_type(value)
        return ItemType[resolved] if resolved else None

    @staticmethod
    def _alias_index(data: dict[str, str]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        ambiguous: set[str] = set()
        for canonical, display in data.items():
            GameCatalog._add_alias(aliases, ambiguous, canonical, canonical)
            GameCatalog._add_alias(aliases, ambiguous, canonical.replace("_", " "), canonical)
            GameCatalog._add_alias(aliases, ambiguous, display, canonical)
            GameCatalog._add_alias(aliases, ambiguous, GameCatalog._tts_alias(display), canonical)
        return aliases

    @staticmethod
    def _add_alias(aliases: dict[str, str], ambiguous: set[str], value: str, canonical: str) -> None:
        normalized = normalize_locale_text(value)
        if not normalized or normalized in ambiguous:
            return
        existing = aliases.get(normalized)
        if existing is None:
            aliases[normalized] = canonical
        elif existing != canonical:
            aliases.pop(normalized)
            ambiguous.add(normalized)

    @staticmethod
    def _tts_alias(value: str) -> str:
        return "".join(char for char in value if char.isalpha() or char.isspace()).strip().replace("  ", " ")

    @classmethod
    def _item_type_alias_index(cls, data: dict[str, str]) -> dict[str, str]:
        aliases = cls._alias_index({key: value for key, value in data.items() if key in ItemType.__members__})
        for member_name, item_type in ItemType.__members__.items():
            if member_name in data:
                continue
            aliases.setdefault(normalize_locale_text(member_name), member_name)
            aliases.setdefault(normalize_locale_text(item_type.value), member_name)
        return aliases

    @staticmethod
    def _unique_alias_index(data: dict[str, dict[str, object]]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        ambiguous: set[str] = set()
        for canonical, metadata in data.items():
            values = [canonical, canonical.replace("_", " ")]
            if isinstance(display_name := metadata.get("display_name"), str):
                values.append(display_name)
            metadata_aliases = metadata.get("aliases", [])
            if isinstance(metadata_aliases, str):
                values.append(metadata_aliases)
            elif isinstance(metadata_aliases, list):
                values.extend(alias for alias in metadata_aliases if isinstance(alias, str))
            for value in values:
                GameCatalog._add_alias(aliases, ambiguous, value, canonical)
        return aliases

    @staticmethod
    def _resolve_alias(value: str, aliases: dict[str, str], *, fuzzy: bool = False) -> str | None:
        normalized = normalize_locale_text(value)
        if not normalized:
            return None
        if canonical := aliases.get(normalized):
            return canonical
        if not fuzzy or not aliases:
            return None
        match = rapidfuzz.process.extractOne(normalized, list(aliases), scorer=rapidfuzz.distance.Levenshtein.distance)
        return aliases[match[0]]

    def resolve_affix(
        self,
        value: str,
        *,
        include_charms: bool = False,
        include_seals: bool = False,
        range_precision: str | None = None,
    ) -> str | None:
        aliases = dict(self._affix_aliases)
        if include_charms:
            aliases.update(self._charm_affix_aliases)
        if include_seals:
            aliases.update(self._seal_affix_aliases)
        resolved = self._resolve_alias(value, aliases, fuzzy=self.grammar.locale == "enUS")
        return resolved or self._resolve_affix_range_precision(value, range_precision, include_charms, include_seals)

    def resolve_affix_exact(
        self,
        value: str,
        *,
        include_charms: bool = False,
        include_seals: bool = False,
        range_precision: str | None = None,
    ) -> str | None:
        aliases = dict(self._affix_aliases)
        if include_charms:
            aliases.update(self._charm_affix_aliases)
        if include_seals:
            aliases.update(self._seal_affix_aliases)
        resolved = self._resolve_alias(value, aliases)
        return resolved or self._resolve_affix_range_precision(value, range_precision, include_charms, include_seals)

    def _resolve_affix_range_precision(
        self, value: str, precision: str | None, include_charms: bool, include_seals: bool
    ) -> str | None:
        canonical = self.grammar.affix_for_range_precision(value, precision)
        if canonical in self.affix_dict:
            return canonical
        if include_charms and canonical in self.charm_affix_dict:
            return canonical
        if include_seals and canonical in self.seal_affix_dict:
            return canonical
        return None

    def resolve_aspect(self, value: str) -> str | None:
        normalized = normalize_locale_text(value)
        matches = [(len(alias), canonical) for alias, canonical in self._aspect_aliases.items() if alias in normalized]
        if matches:
            longest = max(length for length, _ in matches)
            candidates = {canonical for length, canonical in matches if length == longest}
            if len(candidates) == 1:
                return next(iter(candidates))
        equivalent_matches = [
            (len(alias), canonicals)
            for alias, canonicals in self.grammar.aspect_alias_equivalence.items()
            if alias in normalized
        ]
        if not equivalent_matches:
            return None
        longest = max(length for length, _ in equivalent_matches)
        groups = {canonicals for length, canonicals in equivalent_matches if length == longest}
        return min(next(iter(groups))) if len(groups) == 1 else None

    def aspect_names_equivalent(self, left: str, right: str) -> bool:
        return left == right or any(
            left in group and right in group for group in self.grammar.aspect_alias_equivalence.values()
        )

    def resolve_item_type(self, value: str) -> str | None:
        return self._resolve_alias(value, self._item_type_alias_index(self.item_types_dict))

    def resolve_set(self, value: str) -> str | None:
        return self._resolve_alias(value, self._set_aliases)

    def resolve_sigil(self, value: str, *sections: str) -> str | None:
        normalized = normalize_locale_text(value)
        selected_sections = sections or tuple(self._sigil_aliases)
        matches: set[str] = set()
        for section in selected_sections:
            aliases = self._sigil_aliases.get(section, {})
            if canonical := aliases.get(normalized):
                matches.add(canonical)
            for canonical, display in self.affix_sigil_dict_all.get(section, {}).items():
                normalized_display = normalize_locale_text(display)
                if normalized_display and (
                    normalized.startswith(normalized_display) or normalized_display.startswith(normalized)
                ):
                    matches.add(canonical)
        return next(iter(matches)) if len(matches) == 1 else None

    def resolve_tribute(self, value: str) -> str | None:
        return self._resolve_alias(value, self._tribute_aliases)

    def resolve_unique(self, value: str) -> str | None:
        return self._resolve_alias(value, self._unique_aliases)
