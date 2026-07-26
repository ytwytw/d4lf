# Simplified Chinese support plan

[简体中文](zhcn-support-plan.zh-CN.md) | **English**

This document records the engineering and safety decisions for adding `zhCN` Diablo IV support. It is a
working plan, not a claim that the tool is authorized by Blizzard or that an account cannot be actioned.

## Why the earlier multilingual attempt was difficult

The full Git history contains an unmerged Japanese fork commit, `4c22e4b` (`Add Japanese (jaJP) language support`). It added more than 3,000 lines, mostly generated language files, but remained on the stale
`fute/main` ref and did not follow the later seasonal parser changes.

The useful lesson is not that CJK text is impossible. UTF-8 already reaches Python. The hard parts were:

- Item framing still assumed an uppercase Latin item name and English mouse/action-button terminators. The
  Japanese branch added an `Item Power` positional special case rather than a reusable locale grammar.
- Parser rules mixed English literals with a growing set of language-specific tooltip lookups. Each season
  added another place where the fork could drift.
- Language files were delivered as one large snapshot with no source build lock, source hashes, coverage
  report, or automated stale-data check.
- No parser regression tests were added with the Japanese change. The main English parser therefore had no
  protection while localization code changed shared behavior.
- Some generated values were still English placeholders such as `custom type material` and `custom type sigil`. A missing translation could silently become runtime behavior.
- Runtime display text and profile keys were too closely coupled. Changing a localized value could mutate an
  `ItemType` enum or break a user's existing English-keyed profile.

## Architecture

The implementation separates four concerns:

1. **Canonical application IDs.** Existing `enUS` profile keys remain stable IDs. Localized names are aliases
   used only for parsing and display. Loading another locale never mutates enum values.
1. **Locale grammar.** `grammar.json` owns rarity labels, item boundaries, tooltip anchors, and special item
   identifiers. The parser calls grammar operations instead of accumulating CJK-specific branches.
1. **Versioned data adapter.** Companion, d4data, and attributed D2Core inputs are read as explicit UTF-8,
   joined by source identity, hashed, and accompanied by a machine-readable quality report. Ambiguous aliases
   are rejected instead of using first-match behavior.
1. **Fail-closed release gate.** A locale is not automation-ready when its source build is stale, a stable ID
   is missing or new, a source hash changed, an alias is ambiguous, or a required translation is a placeholder.

AI tools can accelerate mapping, test generation, and review, but generated text never bypasses these gates.
An AI guess is not sufficient evidence for an action that can mark, move, use, or drop an item.

### Unified language switch

`general.language` is the single source of truth for both application localization and game parsing. The
Settings window exposes `English (enUS)` and `Simplified Chinese (zhCN)` under **System & Paths**. Changing it:

- rebuilds and retranslates open D4LF windows;
- reloads the matching `assets/lang/<locale>` parser data in the running script handler;
- updates the Diagnostics capture locale; and
- applies the locale safety policy, including stopping any active interaction before locale assets are reloaded.

Display labels are never persisted as configuration values. Controls retain stable IDs such as `zhCN`,
`dark`, and `blacklist`, so translating the UI cannot mutate profiles or parser configuration. The switch does
not modify Diablo IV's own language setting; the user must configure the game client to the same locale.

## Data sources

The full [Diablo4Companion repository](https://github.com/josdemmers/Diablo4Companion) supplies paired `enUS` and
`zhCN` game records with shared SNO/internal-name identity and an MIT license. d4data supplies the existing upstream
build provenance. Its README notes that direct game assets remain Blizzard property.

D2Core supplements affixes, aspects, Uniques, and Talismans when the paired game data has no translation. It is not
the source of truth for catalog membership, and absence from a D2Core snapshot never disables an existing Chinese
alias. The project owner has confirmed direct use and public redistribution with README attribution;
`docs/third-party-data.md` and the public export gate preserve that requirement. Raw snapshots are not committed: a
bounded adapter downloads only eight public static JSON files, verifies the paired `(key, id)` identity sets, locks
their URLs and SHA-256 hashes, and emits per-record translation provenance. It never bypasses the interactive
planner.

D2Core and current d4data identify `shade_damage` and `shadow_damage` as distinct affixes even though the official
Simplified Chinese text for both is `暗影伤害`; the same applies to `poison_damage` and `poisoning_damage` as
`毒素伤害`. The tooltip templates retain one distinguishing signal: one form uses decimal range bounds and the
other integer bounds. `grammar.json` records those narrow rules. The official `malicious` and `virulent` aspect
names are both `恶毒`; they are declared as an explicit equivalent canonical-ID group so either imported ID matches
the same visible game name without inventing a translation.

The current-season scope and source assessment are recorded in `docs/zhcn-scope-audit.md`. Core equipment,
Talisman equipment, and D4LF's optional sigil/tribute filters are separate delivery tiers. Historical non-gear
parser types do not block equipment readiness.

The committed source snapshot records:

- The current Companion checkout is commit `6e52cac` (`Updated data for v3.1.1.72903`), but only the controlled
  `Aspects.enUS.json` changed after its zhCN files were last refreshed for `3.1.0.72592`.
- The local d4data checkout identifies build `3.1.1.72836` at commit `5b68e74`.
- The D2Core static database identifies build `72698`.
- The local grammar-validation reference identifies client build `3.1.0.72810`.

[Blizzard's current patch notes](https://news.blizzard.com/en-us/article/24287406/diablo-iv-patch-notes)
identify the live all-platform client as `3.1.1.72836`, matching d4data. The build
differences must remain visible. It is not valid to relabel `72836` data as `72592`, `72698`, `72810`, or
Companion's repository-level `72903`; a real client capture can validate observed grammar and aliases, but it
cannot prove complete seasonal data coverage.

The source manifest contains all 2,742 runtime stable keys regardless of D2Core coverage. It resolves 2,724 records:
2 equipment records and 16 D4LF extension records remain untranslated. `excluded_historical_records` is zero, so
all existing non-empty Chinese aliases participate in runtime parsing.

The manifest still contains `"runtime_ready": false` for the complete multilingual catalog release gate. Guarded
interaction is enabled for the separately validated equipment scope. Full-catalog promotion remains blocked by
the mixed `72698`/`72810`/`72836`/`72903` source and validation builds and 18 untranslated records; no
current-provider disagreements remain. The known duplicate Chinese aliases are explicitly disambiguated or grouped
and no longer make `source_quality_ok` fail. These are separate, machine-readable findings rather than one opaque
coverage percentage.

Provider conflicts are fail-closed. They are visible in both the locale manifest and quality report and prevent
`runtime_ready=true` until an explicit reviewed resolution is recorded; provider availability or precedence alone
is not release approval.

Five historical non-gear item types (`Elixir`, `Incense`, `Material`, `TemperManual`, and `Tome`) are explicitly
reported as excluded from the equipment milestone. `Nightmare Sigil` is resolved from the public paired
`Type=sigil` identity and no longer needs a client capture merely to discover its item-type label.

## Seasonal update flow

For every patch or season:

1. Fetch both upstream repositories and record exact commits.
1. Fetch and validate the bounded D2Core snapshot; enforce locale pairing and record-count floors, then lock its
   discovered build, URLs, hashes, and derived translation-record index.
1. Read the game-data build from an explicit data-update commit, not the Companion application version.
1. Generate the source manifest, hashes, locale bundle, and quality report into a temporary directory.
1. Compare stable-ID sets and source hashes with the committed lock. Classify additions, removals, renamed
   source text, missing Chinese records, placeholders, and alias collisions.
1. Block promotion if provider builds disagree or any required record is unresolved.
1. Replay checked-in synthetic fixtures and local raw TTS captures offline; never add the raw captures to Git.
1. Run the complete English and localized test suites, lint checks, and release packaging before replacing the
   committed bundle.

This process can be unattended up to the release decision. A new ambiguous term, a source license change, a
new TTS layout, or a build mismatch deliberately requires review.

<a id="account-risk"></a>

## Account risk

Blizzard's current [EULA](https://www.blizzard.com/en-us/legal/fba4d00f-c7e4-4883-b8b9-1b4500a402ea/blizzard-end-user-license-agreement)
and [anti-cheating agreement](https://www.blizzard.com/en-us/legal/cd5930c0-2784-420c-a23d-1e0d6ff8599b/anti-cheating-agreement)
reserve broad discretion over unauthorized third-party programs, automation, and software that facilitates
gameplay. The platform may detect and report an unauthorized program, and account action can include suspension
or closure. D4LF itself also documents that it reads accessibility TTS and, in its normal English mode, sends
mouse and keyboard input.

Therefore no defensible numeric ban probability is available, and neither open source code nor read-only mode
means Blizzard has authorized the software. The risk ordering used by this branch is:

- **Highest:** automated marking, clicking, moving, using, or dropping items while connected to the game.
- **Still material:** running a DLL-based third-party listener in the game process environment, even if the
  consumer only reads text.
- **Lower exposure, not zero:** offline generation and replay after the game is closed.

Normal `zhCN` loot-filter interaction is guarded by the same runtime checks as `enUS`: diagnostic capture blocks
input, every interaction requires Diablo IV to remain the foreground window, and changing locale or starting a
diagnostic capture stops an active interaction. The capture tool only owns the existing named pipe and records
messages emitted by `saapi64.dll`; it does not launch the game, inspect game memory, inject new code, move the
pointer, press keys, or make item decisions. This reduces behavior and blast radius but is not a promise against
detection or account action.

Candidate builds use a distinct `zhcn` prerelease version and keep automatic updates disabled. Re-enable automatic
updates only after `ytwytw/d4lf` has a stable localized release and update feed; otherwise an update could replace
the installed candidate with an incompatible build.

## Client evidence status

Local captures for client build `3.1.0.72810` were reviewed offline and remain outside Git. Two diagnostic
sessions contained 4,224 raw TTS records and 116 complete item frames. The current parser accepted all 116
frames, covering Common, Magic, Rare, Legendary, Unique, and Mythic equipment across 12 equipment types, plus
three Sigil frames. Seventy non-Unique equipment frames also passed both a generated keep filter and a generated
reject filter. The traces included 30 favorite-item prefixes and 22 empty-socket labels.

Seven automatic visual-failure bundles were replayed from their full screenshots. After correcting negative ROI
clipping and left-panel tooltip displacement, every screenshot produced a valid tooltip crop and location-aware
parse. The screenshots and raw records are not publication fixtures because they can contain account-identifying
pixels and text.

The remaining manual evidence is deliberately smaller:

- One packaged-app smoke pass against inventory, equipped, and vendor layouts. Existing captures are primarily
  from the stash and do not prove those three placements end to end.
- One marked-junk item trace. Favorite and socketed items are represented, but no captured item-name prefix
  identifies an already-junk item.
- Separate optional captures for Talisman equipment (charms and seals) and D4LF's non-equipment sigil/tribute
  filters only when those delivery tiers are wanted.
- A manual diagnostic-capture transition check while an interaction is already pending.

Collected traces are replayed offline. They do not become source translations automatically, and personal or
account-identifying metadata must not be recorded.

## D2Core build import

The profile importer accepts public planner links from the [D2Core website](https://www.d2core.com/). Historical
testing used share code `20eK`; its old planner URL now returns `404`, so it is retained as a regression fixture
rather than a live documentation link. The importer reads a public build through the SDK already loaded by the
D2Core page and resolves equipment against D2Core's current `enUS` static catalog. English is used only as a
language-neutral bridge to D4LF's stable IDs, so the generated profile works with either the `enUS` or `zhCN`
game-language setting.

All non-empty equipment variants are imported. Supported fields include equipment type, ordinary and greater
affixes, uniques, legendary aspect upgrades, and transfigured aspect upgrades. Tempered affixes are deliberately
excluded, matching the other build importers. D2Core paragon, skills, mercenaries, consumables, and guide prose
are outside this equipment-import scope. New catalog entries that do not have an exact D4LF stable-ID match are
skipped with a warning instead of being guessed.
