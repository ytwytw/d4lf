# ![D4LF](assets/logo.png)

[简体中文](README.md) | **English**

D4LF is a Windows loot-filter companion for Diablo IV. This branch is based on upstream `v9.3.7` and adds a
Simplified Chinese interface, `zhCN` client parsing, cross-language build imports, localized paragon overlays, and
local diagnostics.

> [!WARNING]
> `9.3.7+zhcn.beta.5` is a beta build. It is not authorized or endorsed by Blizzard, and it cannot guarantee that
> use will not conflict with game rules or anti-cheat systems. Read [Account and automation risk](#account-and-automation-risk).

![D4LF sample](assets/thumbnail.jpg)

## Highlights

- Filter inventory and stash equipment by type, greater affixes, values, rarity, and unique aspects
- Use either the `English (enUS)` or `Simplified Chinese (zhCN)` game client and application interface
- Import builds from Maxroll, Mobalytics, D4Builds, InfinityBuilds, and D2Core
- Import equipment rules and paragon routes through stable internal IDs that work across both locales
- Use highlight/fast vision modes, paragon and information overlays, and guarded item interaction
- Optionally collect local parser-failure samples or manual TTS diagnostics; both are disabled by default

<a id="setup"></a>

## Download And Install

1. Download the latest Windows `.zip` from [this repository's Releases](../../releases) and extract it.
1. Find the Diablo IV installation directory:
   - Battle.net: gear icon on the game page > **Show in Explorer**
   - Steam: game properties > **Installed Files** > **Browse**
1. Run `install_dll.cmd` from the extracted D4LF directory.
1. Provide the Diablo IV path and approve the administrator and local-certificate prompts.
1. Run `d4lf.exe`, then configure the language, game settings, and profiles below.

The [upstream releases](https://github.com/d4lfteam/d4lf/releases) do not contain this branch's complete Chinese
support. See the [full English guide](docs/full-guide.en.md) for extended usage and troubleshooting.

## Required Game Settings

Confirm these Diablo IV settings:

- **Advanced Tooltip Information**: enabled
- **Font Scale**: small or medium
- **HDR**: disabled
- **Use Screen Reader**: enabled
- **Third-Party Screen Reader**: enabled

In D4LF, set **Settings > System & Paths > Interface and Game Language** to match the game client:

- Chinese game client: `Simplified Chinese (zhCN)`
- English game client: `English (enUS)`

This setting changes both the D4LF interface and its item-parser assets. It does not change the Diablo IV client
language. Restart D4LF after changing it. The default loot-filter hotkey is `F11`.

## Import Builds

Paste a supported build URL into the D4LF **Profile Importer**. Supported sources are:

- Maxroll
- Mobalytics
- D4Builds
- InfinityBuilds
- [D2Core](https://www.d2core.com/d4/builds)

The importer maps source-site labels to stable D4LF IDs. An English InfinityBuilds profile can therefore run with a
`zhCN` client, and a Chinese D2Core profile can run with an `enUS` client. A website's display language does not
determine the generated profile's runtime language, and machine-translated site text is not treated as authoritative
Chinese catalog data.

Enable the generated profile under **Settings > Profiles**. Seasonal patches and hotfixes can change equipment,
affixes, and paragon data, so each release still requires manifest checks and representative in-game samples.

## Diagnostics And Privacy

**Automatically Save Recognition Failure Samples** is disabled by default. When enabled, parser failures save a
screenshot, tooltip crop, and matching TTS locally under
`C:/Users/<WINDOWS_USER>/.d4lf/captures/automatic`. D4LF never uploads these files automatically.

The manual diagnostics page is also hidden and disabled by default. Enable **Show Diagnostic Capture Tab** under
**Settings > Advanced** only when needed. Manual diagnostics and automatic failure capture can be enabled together,
but new game-input actions are blocked while a manual capture is active. See the
[Chinese capture guide](docs/zhcn-capture.md).

Review every sample before attaching it to an issue. Do not publish account names, chat, friend lists, or other
personal information. See the [public-release guide](docs/public-release.md) for the repository privacy gate.

## Account And Automation Risk

D4LF reads the screen and accessibility TTS. Optional sorting, marking, and moving features also generate mouse or
keyboard input. Such behavior may be restricted by Blizzard's EULA, terms, or anti-cheat policies. There is no
reliable evidence for a numeric ban probability, and foreground-window or diagnostic input guards do not eliminate
risk.

Use interaction features only after making your own risk assessment. Vision-only mode generally reduces automated
input, but it does not imply official approval or zero risk. See the full
[account-risk assessment](docs/zhcn-support-plan.md#account-risk).

## Data Sources And Attribution

The Simplified Chinese catalog prioritizes stable paired game records and official-client text:

- [Diablo4Companion](https://github.com/josdemmers/Diablo4Companion): primary `enUS`/`zhCN` stable-ID pairs
- [DiabloTools/d4data](https://github.com/DiabloTools/d4data): game-build and internal-identifier validation
- [D2Core](https://www.d2core.com/): licensed supplemental data and cross-checking

D2Core is not the sole source of truth, and a missing D2Core entry never disables an existing Chinese alias. See
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md), [third-party data notes](docs/third-party-data.md), and the
[locale-data update process](docs/locale-data-update.md) for licenses, provenance, and version locks. These projects
and sites do not endorse this branch.

## Development And Verification

The project uses Python 3.14 and `uv`:

```powershell
uv sync --frozen --all-groups
uvx prek run --all-files
uv run pytest -p no:cacheprovider -p no:pytest_randomly
```

GitHub Actions runs seasonal-data candidate checks, public-repository scanning, and Windows builds. See the
[Chinese support audit](docs/zhcn-scope-audit.md) for coverage and remaining in-game checks.

## Project Relationship And Support

This branch is based on [d4lfteam/d4lf](https://github.com/d4lfteam/d4lf) `v9.3.7`. Report Chinese-branch issues in
this repository. Upstream Discord and Ko-fi links in the full guide belong to the original maintainers; they are not
the contact or payment channels of this branch's author.

Released under the [MIT License](LICENSE.txt).
