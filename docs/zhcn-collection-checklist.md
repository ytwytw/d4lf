# zhCN client collection checklist

This is the minimum first-pass evidence needed from a real `zhCN` client. The committed grammar currently references
build `3.1.0.72810`; do not relabel captures made by another build.

The first pass is equipment-only. Non-gear inventory objects are not required, and D4LF's optional sigil and
tribute filters are kept separate from the equipment milestone.

## Safety rules

- Enable `Show Diagnostic Capture Tab` under `Settings > Advanced`, then use the D4LF `Diagnostics` tab for normal
  collection. The setting is disabled by default, and the tab records from the pipe D4LF already owns.
- Do not run the standalone recorder while D4LF is open. Only one process can own `\\.\pipe\d4lf`.
- Do not use automation, macros, scripted hovering, memory inspection, or a game-data dumper.
- Do not record BattleTag, chat, friend lists, account email, or other personal information.
- End each App session with `Stop and Save` and wait for the saved status.

## App workflow

1. Open D4LF, enable `Show Diagnostic Capture Tab` under `Settings > Advanced`, and select the `Diagnostics` tab.
1. Select `Simplified Chinese (zhCN)`, enter or detect the exact four-part game build, and choose a category and area.
1. Select `Start Capture`. New game-input actions are blocked while capture is active.
1. Operate Diablo IV and hover every sample manually.
1. Select `Stop and Save`. D4LF saves the raw JSONL and automatically creates an offline replay report.
1. Use `Open Folder` to open `%USERPROFILE%\.d4lf\captures`.

D4LF generates unique timestamped filenames and never overwrites an earlier capture. Closing the App while a capture
is active also finalizes it. A replay failure does not delete the raw JSONL.

## CLI fallback

The standalone recorder remains available for recovery and development. Close normal D4LF first, then use a separate
JSONL file for each section below. Change only the file and `category` value:

```powershell
uv run python -m src.tools.tts_capture `
  --output .\captures\zhCN-3.1.0.72810-core.jsonl `
  --locale zhCN `
  --game-build 3.1.0.72810 `
  --session-meta area=inventory `
  --session-meta category=core
```

For either workflow, hover each item manually, wait until the screen reader finishes, move away manually, then
continue. It is fine for the recording to contain menus and other noise; the offline replay tool preserves and
bounds it.

## Session 1: framing core

Target: about 12 to 18 ordinary items.

- One common, magic, rare, legendary, unique, and mythic item when available.
- At least one weapon, armor piece, and jewelry item.
- One ancestral item and one non-ancestral item.
- One equipped item and one inventory item.
- One vendor item if it is already convenient to inspect.
- One item with an empty socket, one with an imprinted aspect, and one with a required-level line.

This session confirms the exact Chinese rarity/type header, item-power anchor, affix header, stop markers, and
mouse/action-button terminator. It is the highest-priority capture.

## Session 2: Talisman equipment (optional expansion scope)

Use `category=talisman` only if Lord of Hatred Talisman filtering is part of the desired scope:

- Two charms from different sets.
- Two seals from different rarities or sets, including all spoken affix lines.
- One unique charm or mythic seal if already available.

These are equipment-like filter targets supported by both D4LF and the current in-game loot filter. Do not farm
or purchase missing examples solely for this task.

## Session 3: D4LF extended filters (optional non-equipment scope)

Use `category=extended-filters` only if D4LF's filters beyond equipment are wanted:

- Two nightmare sigils with different dungeon and affix combinations.
- One escalation/bloodied sigil if available.
- Two tributes of different rarity.

The public paired data already maps the Nightmare Sigil item type. These captures are only for the special TTS
layout, dungeon, and affix parsing. They are not required for equipment-only support.

## Do not collect

Do not spend client time on these historical parser types:

- `Elixir` and `Incense`: removed from current Seasonal realms with Lord of Hatred.
- `Material` and `TemperManual`: non-gear and ignored before D4LF profile filtering.
- `Tome`: d4data identifies this as the non-equippable `SkillPointTome`, not a weapon or off-hand.

## Deferred targeted captures

Do not hunt the unresolved aspect or unique list yet. Public current-season sources and stable IDs must be
reconciled first. A later request should name one exact accessible item only when its Chinese TTS text or layout
remains ambiguous after that reconciliation.

## Visual evidence

Raw named-pipe JSONL is more useful than audio or a generic screen recording.

- Take a full-screen PNG only when replay chooses the wrong start/end line, an affix highlight is misplaced, or
  an equipped/shop layout differs from inventory.
- If ordering is impossible to understand from JSONL plus a screenshot, make one short video showing a single
  manual hover. Avoid recording unrelated UI.
- Audio recording is not needed when the UTF-8 TTS text was captured successfully.

## Replay and handoff

The App creates the replay report automatically when `Stop and Save` is selected. For CLI captures, replay each
session only after closing the game:

```powershell
uv run python -m src.tools.tts_replay `
  --input .\captures\zhCN-3.1.0.72810-core.jsonl `
  --assets-dir .\assets\lang\zhCN `
  --output .\captures\zhCN-3.1.0.72810-core-report.json
```

App captures remain under `%USERPROFILE%\.d4lf\captures`. CLI captures and any matching PNG/video can remain under
the repository's ignored `captures/` directory. The raw JSONL is the source of truth. A replay report can always be
regenerated after parser changes.
