# zhCN scope audit for Diablo IV 3.1

[简体中文](zhcn-scope-audit.zh-CN.md) | **English**

This source-snapshot note separates current equipment-filter requirements from historical parser types and from
D4LF's optional non-equipment filters.

## Authoritative product scope

Blizzard's Lord of Hatred loot-filter documentation says the in-game filter applies to gear in drops, inventory,
stash, and vendors. It explicitly excludes non-gear such as Temper manuals, reagents, gems, and currency. Its gear
conditions include item type, rarity, item power, affixes, Codex upgrades, specific Uniques, and Talisman set
bonuses.

Sources:

- <https://news.blizzard.com/en-us/article/24267729/prepare-for-the-reckoning-lord-of-hatred-draws-near>
- <https://news.blizzard.com/en-us/article/24287406/diablo-iv-patch-notes>
- <https://news.blizzard.com/en-gb/article/24271857/diablo-iv-patch-notes-3-0>

The 3.0 notes confirm that Nightmare Dungeon Sigils remain current. The 3.1 notes confirm that Talismans, seals,
and charms remain current, and specifically remove Seal of the Severed Finger by converting existing copies to
Seal of the Golden Epiphany.

## D4LF code paths

- Equipment filtering supports armor, weapons, jewelry, affixes, aspects, Uniques, seals, and charms.
- Sigils and tributes have explicit optional filter sections outside ordinary equipment rules.
- Elixirs, incense, materials, and Temper manuals are ignored before profile filtering.
- `Tome.itt` has no body slot and no weapon class. The only current item that references it is
  `SkillPointTome.itm`. The actual equippable book-style off-hand is `FocusBookOffHand`, displayed as `Focus`.

Therefore `Tome` is classified as a non-equipment consumable in D4LF, not as a weapon.

## External source assessment

### Diablo4Companion

The public paired `enUS`/`zhCN` records remain the best unattended localization input because they carry shared
game identities. Its item-type data already provides a Chinese label for `Nightmare Sigil`; the generator now
joins this by the shared `Type=sigil` identity instead of the old `custom type sigil` placeholder.

Repository: <https://github.com/josdemmers/Diablo4Companion>

### Maxroll

Maxroll is useful for checking which equipment, affixes, aspects, and Uniques appear in active builds. Existing
D4LF importer tests already cover Season 14 guide URLs and Maxroll's Season 14 planner payload. It is not a stable
Chinese localization source, and direct automated page access is robot-restricted in this environment.

Site: <https://maxroll.gg/d4/>

### InfinityBuilds / InfinityTools

InfinityTools separates gear, affixes, aspects, and Uniques from sigils, Tempering, materials, consumables, and
other objects such as tomes. That taxonomy independently supports the equipment/non-equipment boundary. Its
public build-data API is already consumed by D4LF's importer, but the site labels its current build collection as
Season 13 while official and D2Core pages are on Season 14, so it is a cross-check rather than the season authority.

Sites:

- <https://infinitybuilds.gg/en/builds>
- <https://tools.infinitybuilds.gg/en/database>

### D2Core

D2Core's public build listing was current for `S14` and showed all eight current classes when checked. D4LF uses
D2Core's public static database files as a supplemental Chinese source, without automating or bypassing the
interactive planner. D2Core does not define catalog membership: a record absent from its snapshot remains enabled
when another paired source provides Chinese text. The project owner has confirmed direct use and public
redistribution with README attribution. The bounded snapshot contains paired `enUS`/`zhCN` records for 1,008
affixes, 363 aspects, 295 Uniques, and 804 flattened Talisman records at build `72698`. Talisman coverage comprises
365 charms, 11 seals, 45 sets, 110 charm affixes, and 273 seal affixes. Each file is versioned and hashed, and every
locale pair is validated by `(key, id)` before generation.

The attribution and machine-readable publication status are documented in `docs/third-party-data.md` and enforced
by the public export gate.

Site: <https://www.d2core.com/>

## Delivery tiers

1. Core equipment: armor, weapons, jewelry, item headers, affixes, aspects, Uniques, and Mythics.
1. Talisman equipment: seals, charms, their affixes, and set bonuses for Lord of Hatred owners.
1. D4LF extensions: Nightmare/Escalation Sigils and tributes.

Elixirs, incense, materials, Temper manuals, tomes, caches, gems, runes, and currency are outside the zhCN
equipment milestone. They must not block equipment readiness or create client-capture work.
