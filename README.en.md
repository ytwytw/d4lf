# D4LF Simplified Chinese Edition

[简体中文](README.md)

`main` contains the current user-facing version. Install the complete application package from [Releases](https://github.com/ytwytw/d4lf/releases).

D4LF is a Windows desktop item-filtering assistant. It recognizes items from the screen and
Diablo IV accessibility TTS text, then shows keep or junk results from local profiles. This branch
adds Simplified Chinese game parsing, a bilingual interface, and cross-language build imports on top
of upstream [D4LF](https://github.com/d4lfteam/d4lf) V10.

> This is not an official Blizzard tool. No third-party assistant can guarantee zero account risk;
> evaluate and accept that risk before use.

![D4LF interface preview](assets/thumbnail.jpg)

## Main features

- Supports Simplified Chinese and English game clients. The language setting switches both the UI
  and game-text parser.
- Filters equipment by type, item power, rarity, affixes, unique powers, and value thresholds.
- Supports inventory and stash filtering, fast vision mode, match highlighting, the information
  panel, and the Paragon overlay.
- Imports builds from [Maxroll](https://maxroll.gg/d4/),
  [Mobalytics](https://mobalytics.gg/diablo-4/builds), [D4Builds](https://d4builds.gg/),
  [InfinityBuilds](https://infinitybuilds.gg/), and
  [D2Core](https://www.d2core.com/d4/planner).
- Build-source language is independent of game language: English builds work with Chinese or
  English clients, and Chinese D2Core builds work with Chinese or English clients.
- Loot Tools provides a standalone or Profile-linked native game filter editor, full-scope inventory
  export, and an offline equipment reference. See the [usage guide (Chinese)](docs/loot-tools.zh-CN.md).

## Installation

The current version is **`10.0.7+zhcn.2`**, a candidate with no published download yet.
Once released, download the complete application package, including the EXE and assets, from
[Releases](https://github.com/ytwytw/d4lf/releases). See the [release notes (Chinese)](docs/release-notes.zh-CN.md).

1. Extract the complete, version-checked local candidate into a fresh directory. Download public packages
   from this repository's [Releases](https://github.com/ytwytw/d4lf/releases) only after they are published.
1. Locate the Diablo IV installation directory.
1. Close the game first. The installer replaces `saapi64.dll` and may close a running game.
1. Run `install_dll.cmd`, provide the game directory, and allow installation of the local signing
   certificate when prompted.
1. Start `d4lf.exe` and select the language used by the game client under
   `Settings > System > Language`.
1. Enable Advanced Tooltip Information, Use Screen Reader, and 3rd Party Screen Reader in the game.
   Use small or medium font scaling and disable HDR.
1. Import a build or create a profile, then enable the profiles you want in Settings.
1. First enable Vision Mode Only and use fast vision mode to inspect equipped and inventory items without marking them.
1. After reviewing the profile, disable Vision Mode Only to use automation. Default `F11` marks non-matching items;
   it is not a read-only preview.

If TTS never connects, try running the game and launcher as administrator. If the configuration is
invalid, exit D4LF, back up and rename `%USERPROFILE%\.d4lf\params.ini`, and configure it again through Settings.

## Season 15 release and upgrades

This version is based on upstream `10.0.7`, with fixes for build imports, Chinese recognition, and in-app restarts.
Some new items may not be recognized. Items with the same name but different effects need complete descriptions
to identify them. Check recognition in Vision Mode Only before enabling automatic marking.

- Exit D4LF and back up all of `%USERPROFILE%\.d4lf` before upgrading. It contains `params.ini`,
  `profiles`, `native_filters`, `exports\inventory`, and diagnostic captures. Back up files saved elsewhere separately.
- Keep the old complete application directory, and extract the new EXE and assets together into a fresh directory.
  The same Windows account continues to use its existing `.d4lf`; do not copy personal data into the application package.
  Check the version, language, hotkeys, and enabled profiles, then verify recognition in Vision Mode Only.
  For V9 to V10, reimport incompatible profiles.
- Upgrade from older versions by manually extracting the full ZIP to a fresh directory: this release cannot change
  the behavior of an old updater already running.
- This release's `autoupdater.bat` checks this fork only, refuses downgrades, and preserves extra local files.
  A failed copy retains `temp_update` for recovery; manually extract the full release if needed. Do not mix EXE and assets versions.
- App updates do not replace the game's DLL. Rerun `install_dll.cmd` with the game closed only when release notes require a DLL update.
- To roll back, exit the new version, separately back up its current `.d4lf`, and launch the preserved old application.
  If the old version cannot read changed settings or documents, retain both backups and restore the pre-upgrade `.d4lf`.
  Do not mix configuration or assets from different versions. The updater does not downgrade or restore the game DLL;
  follow the older version's installation instructions if its DLL differs.
- Disabling a loot category leaves all of its items untouched, including Mythics. In enabled categories Mythics are kept,
  and favoriting still respects `mark_as_favorite`.

The [Loot Tools guide (Chinese)](docs/loot-tools.zh-CN.md) covers saved files, export statuses,
and troubleshooting. Inventory export primarily preserves TTS text; it does not automatically fill missing fields
from screenshots or read the game's internal state.

## Cross-language build imports

The importer resolves website data to stable internal identifiers before displaying names in the
selected UI and game language. As a result:

| Build source                                             | Chinese client | English client |
| -------------------------------------------------------- | -------------- | -------------- |
| English Maxroll, Mobalytics, D4Builds, or InfinityBuilds | Supported      | Supported      |
| Chinese D2Core                                           | Supported      | Supported      |

Entries that cannot be matched exactly after a website or season update are skipped and logged
instead of being guessed from a fuzzy translation. Review imported results in the profile editor.

## Data and acknowledgements

Thanks to [D4LF](https://github.com/d4lfteam/d4lf), [D2Core](https://www.d2core.com/d4/planner),
and the community data projects. Equipment references are offline snapshots; missing names, drop locations,
and probabilities remain unknown. See the [data notice](assets/equipment_knowledge/NOTICE.md) for sources,
versions, and attribution.

## Diagnostics and privacy

- Automatic failure capture is off by default.
- The standalone Diagnostics page is hidden by default and must be enabled explicitly in Advanced
  Settings.
- Captures and diagnostics stay on the local machine under `%USERPROFILE%\.d4lf\captures`.
- These features do not upload data or record the microphone.
- Automatic capture stores only the relevant screenshot, TTS text, and manifest after a recognition
  failure. Manual diagnostic recording can be started and stopped independently.

Screenshots can contain character names, chat, or other screen content. Review and redact captures
before attaching them to a public issue.
Inventory exports also remain local. Share only the relevant, redacted information when reporting a problem;
you do not need to share the entire `.d4lf` directory.

## Settings and profile rules

The [detailed interface and profile guide](README.md#%E7%95%8C%E9%9D%A2%E4%B8%8E%E9%85%8D%E7%BD%AE) includes English descriptions of settings,
filter syntax, the Paragon overlay, and the information panel.

## Reporting problems

See [LICENSE](LICENSE) for licensing. Use
[GitHub Issues](https://github.com/ytwytw/d4lf/issues) for bug reports and improvements.
