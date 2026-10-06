"""Find legacy affix pools that ask for more matches than they list."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.profiles import ProfileModel


def oversized_pools(profile: ProfileModel) -> list[str]:
    """Describe every pool whose minCount exceeds its listed affixes (evaluated as "all listed")."""
    findings: list[str] = []
    for section, groups in (("Affixes", profile.affixes), ("Seals", profile.seals), ("Charms", profile.charms)):
        for group in groups:
            for rule_name, spec in group.root.items():
                for pool_name in ("affix_pool", "inherent_pool"):
                    for index, pool in enumerate(getattr(spec, pool_name, None) or [], 1):
                        if pool.min_count > len(pool.count):
                            findings.append(
                                f"{section}.{rule_name}.{pool_name}[{index}] minCount {pool.min_count} "
                                f"exceeds its {len(pool.count)} listed affixes"
                            )
    return findings
