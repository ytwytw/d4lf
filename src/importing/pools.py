"""Imported affix pools never demand more than the imported data can prove.

A source rule asks for ``required`` of the affixes it lists. When some listed affixes could not be imported,
an item may satisfy the source rule with exactly those unknown affixes, so each unresolved affix lowers the
requirement on the imported ones by one. When nothing is left to require, the pool is dropped and the slot
rule keeps every item it otherwise matches (a visible, deliberately broad rule) instead of being omitted.
"""

import logging
from typing import TYPE_CHECKING

from src.item import AffixType
from src.profiles import AffixFilterCountModel, AffixFilterModel

if TYPE_CHECKING:
    from src.item import Affix

LOGGER = logging.getLogger(__name__)
REQUIRED_EQUIPMENT_AFFIXES = 3


def required_known_affixes(required: int, resolved: int, unresolved: int) -> int:
    """Imported affixes an item must show if it met ``required`` of ``resolved + unresolved`` source affixes."""
    return max(0, min(required, resolved + unresolved) - unresolved)


def import_pool(
    affixes: list[Affix], required: int, unresolved_count: int = 0, *, context: str = ""
) -> list[AffixFilterCountModel]:
    known = required_known_affixes(required, len(affixes), unresolved_count)
    label = context or "Imported rule"
    if unresolved_count and known == 0:
        LOGGER.warning(
            "%s: %d source affix(es) could not be imported, so no imported affix is required; the rule now keeps "
            "every item it otherwise matches. / %s：%d 个来源词缀无法导入，因此不再要求任何已导入词缀；"
            "此规则现在保留其他条件匹配的所有物品。",
            label,
            unresolved_count,
            label,
            unresolved_count,
        )
    elif unresolved_count:
        LOGGER.warning(
            "%s: %d source affix(es) could not be imported; requiring %d of the %d imported affixes. / "
            "%s：%d 个来源词缀无法导入；改为要求 %d 个已导入词缀中的 %d 个。",
            label,
            unresolved_count,
            known,
            len(affixes),
            label,
            unresolved_count,
            len(affixes),
            known,
        )
    if not affixes or known == 0:
        return []
    count = [AffixFilterModel(name=affix.name, want_greater=affix.type == AffixType.greater) for affix in affixes]
    return [AffixFilterCountModel(count=count, minCount=known)]


__all__ = ["REQUIRED_EQUIPMENT_AFFIXES", "import_pool", "required_known_affixes"]
