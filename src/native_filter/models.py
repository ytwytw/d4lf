"""Editable native loot-filter documents, independent of D4LF profiles."""

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class Action(IntEnum):
    SHOW = 0
    HIDE_LABEL = 1
    RECOLOR = 2
    HIDE_ALL = 3


class ConditionKind(StrEnum):
    ITEM_POWER = "itemPower"
    RARITY = "rarity"
    PROPERTIES = "itemProperties"
    CODEX = "codexUpgrade"
    GREATER_AFFIX = "greaterAffix"
    ITEM_TYPES = "itemTypes"
    REQUIRED_AFFIXES = "requiredAffixes"
    OPTIONAL_AFFIXES = "optionalAffixes"
    SPECIFIC_ITEMS = "specificItems"
    TALISMAN_SET = "talismanSetBonus"
    UNKNOWN = "unknown"


KINDS = tuple(kind for kind in ConditionKind if kind != ConditionKind.UNKNOWN)
MAX_RULES = 25


@dataclass
class Condition:
    kind: ConditionKind
    sno_ids: tuple[int, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    mask: int = 0
    min_count: int = 1
    ga_sno_ids: tuple[int, ...] = ()
    set_sno_id: int | None = None
    piece_sno_ids: tuple[int, ...] = ()
    unknown_type: int | None = None


@dataclass
class Rule:
    name: str = "新规则"
    action: int = Action.SHOW
    color_hex: str = "#0000ff"
    enabled: bool = True
    conditions: list[Condition] = field(default_factory=list)


@dataclass
class NativeFilter:
    name: str = "D4LF 过滤器"
    rules: list[Rule] = field(default_factory=lambda: [Rule("显示所有物品")])
    raw_f3: int | None = 5
    raw_f4: int | None = 1
    original_payload: bytes = field(default=b"", repr=False, compare=False)
    original_digest: str = field(default="", repr=False, compare=False)
    opaque: bool = False

    @property
    def hides_items(self) -> bool:
        return any(rule.enabled and rule.action in {Action.HIDE_ALL, Action.HIDE_LABEL} for rule in self.rules)


@dataclass
class CompilationResult:
    document: NativeFilter
    warnings: tuple[str, ...]
    profile_name: str
    profile_digest: str
    game_version: str
    strict: bool = False


class NativeFilterError(ValueError):
    """An invalid or unsafe native filter could not be processed."""
