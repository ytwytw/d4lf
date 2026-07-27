# D4LF Simplified Chinese Edition

[简体中文](README.md)

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

## Installation

1. Download and extract the latest ZIP from this repository's
   [Releases](https://github.com/ytwytw/d4lf/releases).
1. Locate the Diablo IV installation directory.
1. Run `install_dll.cmd`, provide the game directory, and allow installation of the local signing
   certificate when prompted.
1. Start `d4lf.exe` and select the language used by the game client under
   `Settings > System > Language`.
1. Enable Advanced Tooltip Information, Use Screen Reader, and 3rd Party Screen Reader in the game.
   Use small or medium font scaling and disable HDR.
1. Import a build or create a profile, then enable the profiles you want in Settings.
1. Start the game and use the hotkeys shown on the main screen. `F11` runs item filtering by default.

If TTS never connects, try running the game and launcher as administrator. If the configuration is
invalid, exit D4LF, delete `%USERPROFILE%\.d4lf\params.ini`, and configure it again through Settings.

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

Chinese data is aggregated from multiple sources around stable internal identifiers. No third-party
website is treated as the sole source of truth. D2Core data is used with permission as supplemental
data and as a build source; thanks to [D2Core](https://www.d2core.com/d4/planner) for its reference
data and support. Changes after a game or season update still need verification against real client
text and other reliable sources.

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

## Development

The project uses Python 3.14, [uv](https://docs.astral.sh/uv/), and PyQt6, and targets Windows.

```powershell
uv sync
uv run pytest . -m "not selenium" -n logical
uv run prek run -a
```

See [LICENSE](LICENSE) for licensing. Use
[GitHub Issues](https://github.com/ytwytw/d4lf/issues) for bug reports and improvements.
