![Classic upstream D4LF logo](assets/logo.png)

# D4LF Simplified Chinese Edition

[简体中文](README.md)

`main` contains the current user-facing version. Install the complete application package from [Releases](https://github.com/ytwytw/d4lf/releases).

D4LF is a Windows desktop item-filtering assistant. It recognizes items from the screen and
Diablo IV accessibility TTS text, then shows keep or junk results from local profiles. This branch
adds Simplified Chinese game parsing, a bilingual interface, and cross-language build imports on top
of upstream [D4LF](https://github.com/d4lfteam/d4lf) V10.

> This is not an official Blizzard tool. No third-party assistant can guarantee zero account risk;
> evaluate and accept that risk before use.

See [actual screenshots of the Chinese edition](README.md#%E7%95%8C%E9%9D%A2%E4%B8%8E%E9%85%8D%E7%BD%AE), including the main window, settings,
filter generator, inventory export, and equipment reference. Build names and some labels retain their source language.

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
   `Settings > System & Paths > Language`.
1. Enable Advanced Tooltip Information, Use Screen Reader, and 3rd Party Screen Reader in the game.
   Use small or medium font scaling and disable HDR.
1. Import a build or create a profile, then enable the profiles you want on the main screen.
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

Use **Settings** for automation, loot categories, stash and transfer, appearance, language, and hotkeys.
Enable **Vision Mode Only** under **Automation** when first checking recognition. Under **UI & Theme**,
choose **Highlight Matches** to frame matching affixes on the tooltip, or **Fast** to show the result directly.

The [Chinese interface guide](README.md#%E7%95%8C%E9%9D%A2%E4%B8%8E%E9%85%8D%E7%BD%AE) uses current screenshots. The detailed YAML and overlay reference follows.

## How to filter / Profiles

All profiles define whitelist filters. If no filter included in your profiles matches an item in an enabled filterable
item category, it will be marked as junk (or dropped in drop mode). Disabled categories are left untouched, including Mythics.

Your config files will be validated on startup and will prevent the program from starting if the structure or syntax is
incorrect. The error message will provide hints about the specific problem.

The following sections will explain each type of filter that you can specify in your profiles. How you define them in
your YAML files is up to you; you can put all of these into just one file or have a dedicated file for each type of
filter, or even split the same type of filter over multiple files. Ultimately, all profiles specified in
the main-screen profile list will be used to determine if an item should be kept when its category is enabled. If one
of the profiles wants to keep the item, it will be kept regardless of the other profiles. Similarly, if a filter is missing in all profiles (e.g., there is
no `Sigils` section in any profile), all corresponding items (in this case, sigils) will be kept when Sigils filtering is enabled.

### Affix / Unique Aspect Filter Syntax

You have two choices on how to specify aspects or affixes of an item. For both options we recommend importing a profile first and then working from there.

- You can use the Edit Profile window in the GUI, which is the recommended approach
- You can also manually edit your profile.

The instructions below are all about editing the file manually, but the explanations apply to the GUI as well.

<details><summary>Examples</summary>

```yaml

# Filter for attack speed
- { name: attack_speed }
# Filter for attack speed with a threshold value.
# The filter keeps larger rolls when the tooltip range increases and smaller rolls when the range decreases.
- { name: attack_speed, value: 4 }
# Filter for attack speed where the affix is greater than 50% of the potential maximum
- { name: attack_speed, minPercentOfAffix: 50 }
```

</details>

### Affixes

Affixes are defined by the top-level key `Affixes`. It contains a list of filters that you want to apply. Each filter
has a name and can filter for any combination of the following:

- `itemType`: The name of the type or a list of multiple types.
  See [assets/lang/enUS/item_types.json](assets/lang/enUS/item_types.json)
- `rarity`: A single rarity or a list of rarities the rule should match. An empty/absent value matches all rarities. Values
  are case-insensitive. See [Filtering on rarity](#filtering-on-rarity) for details and the list of rarities
  in [rarity.py](https://github.com/d4lfteam/d4lf/blob/v10.0.3/src/game_data/rarity.py)
- `minPower`: Minimum item power
- `minGreaterAffixCount`: Minimum number of greater affixes expected on the overall item. See [Greater Affix Filtering](#greater-affix-filtering) for more information on filtering GAs.
- `affixPool`: A list of multiple different rulesets to filter for. Each ruleset must be fulfilled or the item is
  discarded
  - `count`: Define a list of affixes (see [syntax](#affix--unique-aspect-filter-syntax)) and
    optionally `minCount` and `maxCount`
    - `minCount`: specifies the minimum number of affixes that must match the item. defaults to amount of specified
      affixes
    - `maxCount` specifies the maximum number of affixes that must match the item. defaults to amount of specified
      affixes
- `inherentPool`: The same rules as for `affixPool` apply, but this is evaluated against the inherent affixes of the
  item
- `uniqueAspect`: If you're looking for a specific unique, this is how you define it. It has the following properties:
  - `name`: (Required) The name of the unique you are looking for. You can find a list in [uniques.json](assets/lang/enUS/uniques.json)
  - `value`: What is the minimum value the aspect must have. You can not have both this and minPercentOfAspect
  - `minPercentOfAspect`: Instead of defining a specific value, what percent of the potential maximum value of the aspect should we keep. See [this section](#filtering-on-percent-of-affix-instead-of-value) for more information.

<details><summary>Config Examples</summary>

```yaml
Affixes:
  # Search for chest armor and pants that are at least item level 725
  # and have at least 3 affixes of the affixPool
  - NiceArmor:
      itemType: [ chest armor, pants ]
      minPower: 725
      affixPool:
        - count:
            - { name: dexterity, value: 33 }
            - { name: damage_reduction, value: 5 }
            - { name: lucky_hit_chance, value: 3 }
            - { name: total_armor, value: 9 }
            - { name: maximum_life, value: 700 }
          minCount: 3

  # Search for chest armor that is at least item level 900 and have at least 3 affixes of the affixPool.
  # The item must have 2 greater affixes, but note they do not need to be from the affixPool.
  # See Greater Affix Filtering section for more information on filtering GAs
  - NiceArmor:
      itemType: chest armor
      minPower: 900
      minGreaterAffixCount: 2
      affixPool:
        - count:
            - { name: dexterity }
            - { name: damage_reduction }
            - { name: lucky_hit_chance }
            - { name: total_armor }
            - { name: maximum_life }
          minCount: 3

  # Search for boots that have at least 2 of the specified affixes and either max evade charges or reduced evade cooldown as inherent affix
  - GreatBoots:
      itemType: boots
      minPower: 800
      inherentPool:
        - count:
            - { name: maximum_evade_charges }
            - { name: attacks_reduce_evades_cooldown_by_seconds }
          minCount: 1
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }
            - { name: cold_resistance }
            - { name: lightning_resistance }
          minCount: 2

  # Search for boots that have at least 2 of the specified affixes AND are a Penitent Greaves
  # The Greaves must have at least 50% of the possible roll range for its unique aspect
  # Note this would not match non-unique boots that have movement speed and cold resistance, it will only match a Penitent Greaves
  - GreatUniqueBoots:
      itemType: boots
      minPower: 800
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }
            - { name: cold_resistance }
            - { name: lightning_resistance }
          minCount: 2
      uniqueAspect:
        - name: penitent_greaves
          minPercentOfAspect: 50

  # You can also search for multiple unique aspects at once, e.g. to keep several BiS uniques regardless of build
  # Keep all penitent greaves or gohrs_devastating_grips with 900 power
  - HighPowerUniques:
      minPower: 900
      uniqueAspect:
        - name: penitent_greaves
        - name: gohrs_devastating_grips

  # Search for boots with movement speed and 1 resistances from a pool of all resistances.
  # No need to add maxCount to the resistance group since it isn't possible for an item to have more than one resistance affix
  - ResBoots:
      itemType: boots
      minPower: 800
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }
        - count:
            - { name: shadow_resistance }
            - { name: cold_resistance }
            - { name: lightning_resistance }
            - { name: fire_resistance }
            - { name: poison_resistance }
          minCount: 1

  # Search for boots with movement speed. At least two of all item affixes must be a greater affix, but we don't care which
  - GreaterAffixBoots:
      itemType: boots
      minPower: 800
      minGreaterAffixCount: 2
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }

  # Keep all ancestral items, even if they don't match a different filter
  - AncestralMatch:
      minPower: 900
```

</details>

Affix names are lower case and spaces are replaced by underscore. You can find the full list of names
in [assets/lang/enUS/affixes.json](assets/lang/enUS/affixes.json).

### Filtering on rarity

Use `rarity` to restrict an affix rule to specific item rarities.

- If `rarity` is omitted, the rule matches all rarities.
- `rarity` accepts one value (`rarity: rare`) or a list (`rarity: [common, magic, rare]`).

The valid rarities are listed in [rarity.py](https://github.com/d4lfteam/d4lf/blob/v10.0.3/src/game_data/rarity.py).

<details><summary>Config Examples</summary>

```yaml
Affixes:
  # Only keep RARE chest armor with these affixes. A legendary with the same affixes is NOT kept by this rule.
  - RareCraftBase:
      itemType: chest armor
      rarity: rare
      affixPool:
        - count:
            - { name: dexterity }
            - { name: maximum_life }
            - { name: total_armor }
          minCount: 2

  # Keep common, magic or rare boots as craft candidates
  - CraftBoots:
      itemType: boots
      rarity: [common, magic, rare]
      affixPool:
        - count:
            - { name: movement_speed }
          minCount: 1
```

</details>

### Filtering on percent of affix instead of value

You also have the option to filter on the minimum percent of the affix you want instead of a specific value. For example, say you want strength on an item. The potential values for strength are 100-150. If you say the `minPercentOfAffix` for strength is 50 (which means 50%), then strength rolls of 125 and up are kept and rolls below 125 would be discarded.

A greater affix is considered to always match a `minPercentOfAffix`. You do not need to designate larger/smaller for `value` or `minPercentOfAffix`; that is automatically determined from the roll range.

If you put in `minPercentOfAffix` you can not also put `value` for that affix. It must be one or the other.

These rules also apply for `minPercentOfAspect` on the `uniqueAspect` and in `GlobalUniques`.

<details><summary>Config Examples</summary>

```yaml
Affixes:
  # Search for chest armor that is at least item level 925 and have at least 3 affixes of the affixPool.
  # It must have at least 40 damage_reduction, and armor must be at least 70% of its potential maximum affix value
  - NiceArmor:
      itemType: chest armor
      minPower: 925
      affixPool:
        - count:
            - { name: dexterity }
            - { name: damage_reduction, value: 40 }
            - { name: lucky_hit_chance }
            - { name: armor, minPercentOfAffix: 70 }
            - { name: maximum_life }
          minCount: 3

```

</details>

### Greater Affix Filtering

D4LF provides two complementary ways to filter items based on Greater Affixes:

#### 1. Item-Level Greater Affix Count (`minGreaterAffixCount`)

This filter requires a minimum total number of Greater Affixes on the entire item, regardless of which affixes they are.

<details><summary>Example</summary>

```yaml
Affixes:
  - GreaterAffixBoots:
      itemType: boots
      minGreaterAffixCount: 2  # Item must have at least 2 Greater Affixes total
      affixPool:
        - count:
            - { name: movement_speed }
            - { name: maximum_life }
            - { name: strength }
            - { name: fire_resistance }
          minCount: 3
```

</details>

#### 2. Per-Affix Greater Affix Requirements (`want_greater`)

When using the Profile Editor GUI or when importing affixes using the importer, you can mark/import specific affixes
with a "Greater" checkbox. This is shown as `want_greater` in the profile. This is a list of affixes that you would prefer
to be greater affixes. The `minGreaterAffixCount` value on the item is still respected, so if you have two affixes tagged
as `want_greater` but a `minGreaterAffixCount` of 1, an item with one of those two affixes as GA will be kept. If neither
of those affixes are GA but a different one is, the item will not be kept.

<details><summary>Example</summary>

```yaml
Affixes:
  - PerfectBoots:
      itemType: boots
      affixPool:
        - count:
            - { name: movement_speed, want_greater: true }  # MUST be a Greater Affix
            - { name: maximum_life, want_greater: true }    # MUST be a Greater Affix
            - { name: strength }                            # Can be normal or Greater
            - { name: fire_resistance }                      # Can be normal or Greater
          minCount: 3
      minGreaterAffixCount: 2  # Auto-set by GUI if Auto-Sync is checked, or Require Greater Affixes is checked on the importer
```

**This item would match:** Boots with movement_speed (GA), maximum_life (GA), cold_resistance (normal), fire_resistance (normal)\
**Why:** movement_speed and maximum_life are both Greater Affixes as required, and item has 4 affixes (meets minCount of 3)

**This item would NOT match:** Boots with movement_speed (normal), maximum_life (GA), cold_resistance (normal), fire_resistance (normal)\
**Why:** movement_speed is marked as `want_greater: true` but is not a Greater Affix on the item

</details>

#### Common Use Cases

<details><summary>Examples</summary>

**"I want boots with at least 2 Greater Affixes, don't care which ones"**

```yaml
- itemType: boots
  minGreaterAffixCount: 2
  affixPool:
    - count:
        - { name: movement_speed }
        - { name: maximum_life }
        - { name: strength }
        - { name: fire_resistance }
      minCount: 3
```

**"I want boots where movement_speed MUST be a Greater Affix"**

```yaml
- itemType: boots
  minGreaterAffixCount: 1  # The minGreaterAffixCount is important, if it was 0 then movement_speed would not be required to be GA
  affixPool:
    - count:
        - { name: movement_speed, want_greater: true }
        - { name: maximum_life }
        - { name: strength }
        - { name: fire_resistance }
      minCount: 3
```

**"I want boots where both movement_speed AND maximum_life MUST be Greater Affixes"**

```yaml
- itemType: boots
  minGreaterAffixCount: 2  # minGreaterAffixCount of 2 requires both to be GA
  affixPool:
    - count:
        - { name: movement_speed, want_greater: true }
        - { name: maximum_life, want_greater: true }
        - { name: strength }
        - { name: fire_resistance }
      minCount: 3
```

**"I want boots where either movement_speed OR maximum_life are Greater Affixes"**

```yaml
- itemType: boots
  minGreaterAffixCount: 1  # minGreaterAffixCount of 1 requires either to be GA
  affixPool:
    - count:
        - { name: movement_speed, want_greater: true }
        - { name: maximum_life, want_greater: true }
        - { name: strength } # If strength on the item was greater and the top two were not, this would not be matched
        - { name: fire_resistance }
      minCount: 3
```

</details>

### Seals and Charms

Seals and charms are defined by the top-level keys `Seals` and `Charms`. If no seal or charm filter is
provided, all items of that type will be kept.

Both sections support:

- `rarity`: A single rarity or a list of rarities the rule should match.
- `minGreaterAffixCount`: Minimum number of greater affixes expected on the seal or charm.
- `affixPool`: The same rule structure used by item affix filters, but matched against seal or charm affixes.
- `uniqueAspect`: For unique charms or mythic seals.

`Charms` additionally support:

- `set`: One or more charm set names. A charm with any listed set will match.

Seal affix names are listed in [assets/lang/enUS/seals_affixes.json](assets/lang/enUS/seals_affixes.json). Charm affix
names are listed in [assets/lang/enUS/charms_affixes.json](assets/lang/enUS/charms_affixes.json). Charm set names are
listed in [assets/lang/enUS/sets.json](assets/lang/enUS/sets.json). Unique charm and mythic seal names use the same
[uniques.json](assets/lang/enUS/uniques.json) list as other unique filters.

<details><summary>Config Examples</summary>

```yaml
Seals:
  # Keep seals with either cooldown_reduction, the berserkers crucible specific affix
  # berserking duration, or a charm slot. Note the name of the required set is in the affix.
  - UtilitySeal:
      affixPool:
        - count:
            - { name: cooldown_reduction }
            - { name: berserkers_crucible_berserking_duration }
            - { name: charm_slot }
          minCount: 1

  # Keep this specific mythic seal
  - Mythic Seal:
      uniqueAspect:
        - name: seal_of_the_diamond_mind

Charms:
  # Keep any charm from the Might of the Den Mother set.
  - DenMotherSet:
      set: [might_of_the_den_mother]

  # Keep Arreat's Bearing with maximum life.
  - ArreatsBearing:
      affixPool:
        - count:
          - { name: maximum_life }
      uniqueAspect:
        - name: arreats_bearing

  # Keep rare charms with maximum_life.
  - RareLifeCharm:
      rarity: rare
      affixPool:
        - count:
            - { name: maximum_life }
```

</details>

Mythic seals and charms are kept without matching a profile when their category is enabled; disabled categories are untouched.

### AspectUpgrades

Legendary Aspects that you want to be notified of receiving upgrades for can be placed in your profile.
They are defined in the top-level key `AspectUpgrades`.

This filter is generally for build-specific aspects that you'd like to be made aware of when you receive an upgrade so you can
upgrade that aspect immediately at the occultist. We notify the user by favoriting the item and showing orange text or
orange highlighting when hovering over the item.

If the item matches any other profile, this filter does nothing. This filter does respect the `mark_as_favorite` config property.
Any aspects that do not match this filter or are not codex upgrades are handled by the `keep_aspects` config property.

<details><summary>Config Examples</summary>

```yaml
AspectUpgrades:
  # This would mark Snowveiled Adventurer's Pants as a favorite if it's a codex upgrade. It would ignore the pants otherwise.
  - of_singed_extremities
  - snowveiled
```

```yaml
# This works exact same as above, it's just a different way to format it
AspectUpgrades: [of_singed_extremities, snowveiled]
```

</details>

Aspect names are lower case and spaces are replaced by underscore. You can find the full list of names
in [assets/lang/enUS/aspects.json](assets/lang/enUS/aspects.json).

### Sigils

Sigils are defined by the top-level key `Sigils`. It contains a mapping of blacklist and/or whitelist rules for affix or
location names. If no Sigil filter is provided, all Sigils will be kept.

<details><summary>Config Examples</summary>

```yaml
Sigils:
  blacklist:
    # locations
    - endless_gates
    - vault_of_the_forsaken

    # affixes
    - armor_breakers
    - resistance_breakers
```

If you want to filter for a specific affix or location, you can also use the `whitelist` key. Even if `whitelist` is
present, `blacklist` will be used to discard sigils that match any of the blacklisted affixes or locations.

```yaml
# Only keep sigils for vault_of_the_forsaken without any of the affixes armor_breakers and resistance_breakers
Sigils:
  blacklist:
    - armor_breakers
    - resistance_breakers
  whitelist:
    - vault_of_the_forsaken
```

To switch that priority, you can add the `priority` key with the value `whitelist`.

```yaml
# This will keep all vault of the forsaken sigils even if they have armor_breakers or resistance_breakers
Sigils:
  blacklist:
    - armor_breakers
    - resistance_breakers
  whitelist:
    - vault_of_the_forsaken
  priority: whitelist
```

You can also create conditional filters based on a single affix or location.

```yaml
# Only keep sigils for iron_hold when it also has shadow_damage
Sigils:
  blacklist:
    - armor_breakers
    - resistance_breakers
  whitelist:
    - [ iron_hold, shadow_damage ]
```

</details>

You can gate sigils by rarity with top-level `rarity`. Sigil rarity is derived from sigil affixes using
[assets/lang/enUS/sigils.json](assets/lang/enUS/sigils.json).

- If `rarity` is omitted, all sigil rarities pass.
- A sigil matches when its rarity is listed **or** it matches a whitelist rule.
- Blacklist rules still discard matching sigils, subject to the configured priority.
- If rarity cannot be resolved, only the whitelist branch can match.

```yaml
# Only keep rare sigils, and among those discard armor_breakers / resistance_breakers
Sigils:
  rarity: rare
  blacklist:
    - armor_breakers
    - resistance_breakers
```

Sigil affixes and location names are lower case and spaces are replaced by underscore. You can find the full list of
names in [assets/lang/enUS/sigils.json](assets/lang/enUS/sigils.json).

### Tributes

Tributes are defined by the top-level key `Tributes`. Use an object with `name` and/or `rarity` keys.
A tribute is kept if its name is in the `name` list **or** its rarity is in the `rarity` list.
Omitting a key means that dimension is not checked at all. If no `Tributes` filter is provided, all tributes are kept.

Mythic tributes are kept without matching a profile when tribute filtering is enabled; otherwise they are untouched.

<details><summary>Config Examples</summary>

```yaml
# Keeps only tribute_of_harmony
Tributes:
  name: [tribute_of_harmony]
```

If you're exceptionally pressed for time, you can just put the name of the tribute without "tribute_of\_" at the beginning.

```yaml
# Keeps Tribute of Harmony and Tribute of Ascendance (Resolute)
Tributes:
  name: [harmony, ascendance_resolute]
```

You can also filter by rarity. The valid rarities are listed in [rarity.py](https://github.com/d4lfteam/d4lf/blob/v10.0.3/src/game_data/rarity.py).

```yaml
# Keeps only legendary and unique tributes
Tributes:
  rarity: [legendary, unique]
```

When both keys are provided, a tribute is kept if it matches **either** the name list or the rarity list.

```yaml
# Keeps tribute_of_harmony OR all legendary/unique tributes
Tributes:
  name: [harmony]
  rarity: [legendary, unique]
```

</details>

Tribute names are lower case and spaces are replaced by underscore. Parentheses are removed. Note that United and
Resolute identifiers are part of the names in [assets/lang/enUS/tributes.json](assets/lang/enUS/tributes.json). You can find the list of item rarities
in [rarity.py](https://github.com/d4lfteam/d4lf/blob/v10.0.3/src/game_data/rarity.py)

### GlobalUniques

If you are searching for a specific Unique, use the `uniqueAspect` key in [the Affixes section](#affixes). If you
additionally want to keep other uniques that have particular stats, use the `GlobalUniques` key.

Global unique filters are defined by the top-level key `GlobalUniques`. It contains a list of parameters that you want
to filter for. If no global unique filter is provided or if the item does not match any unique filter (affix or otherwise),
uniques will be handled according to the handle_uniques configuration. Mythics in enabled categories are kept regardless of
profile matching; marking kept items as favorites still depends on `mark_as_favorite`. Disabled categories are untouched.

The following global filters are available:

- `minGreaterAffixCount`: Only keep uniques with a specific number of greater affixes
- `minPercentOfAspect`: Only keep uniques whose aspect is above a percentage of the total possible.
  For example, if this is set to 80 and an aspect has a range of 100-200, then a value of 180 would be kept but a value
  of 150 would be marked as junk. Situations where a smaller value is what is wanted are automatically handled as well.
- `minPower`: The minimum item power of uniques to keep
- `profileAlias`: In vision mode, uniques show as <filename>.<aspect>. For example myuniques.yaml with fists_of_fate aspect defined
  would show as myuniques.fists_of_fate. The label for the filename can be configured at the aspect level using the
  profileAlias flag (see examples).

<details><summary>Config Examples</summary>

```yaml
# Take all uniques with item power 900 or higher
GlobalUniques:
  - minPower: 900
```

```yaml
# Take all uniques with at least 1 greater affix. It would show in logs/vision mode as cool_stuff.<name of unique>
GlobalUniques:
  - minGreaterAffixCount: 1
    profileAlias: cool_stuff
```

```yaml
# Note that if a unique matches any filter, it is kept. Each - denotes a new filter.
# For example, the below will keep all uniques that have two greater affixes OR an aspect percentage greater than 80
GlobalUniques:
  - minGreaterAffixCount: 2
  - minPercentOfAspect: 80
```

```yaml
# Conversely, this will match all uniques that have two greater affixes AND an aspect percentage greater than 80
GlobalUniques:
  - minGreaterAffixCount: 2
    minPercentOfAspect: 80
```

</details>

## Paragon overlay

Upstream historical example using the English game client; not a screenshot of the Chinese edition.

![Upstream Paragon overlay, English client](assets/paragon_overlay.jpg)

D4LF can import Paragon boards from supported build planners and show them in-game using the Paragon overlay.

**How to use**

1. Import your build from a supported planner (Mobalytics / Maxroll / D4Builds / InfinityBuilds).
1. Enable **Import Paragon** in the importer. Paragon data will be stored in your profile YAMLs in the profiles folder (default: `~/.d4lf/profiles`).
1. Toggle the Paragon overlay using the hotkey (default **F10**, configurable in *Advanced options*).
1. Follow the on-screen instructions to zoom in and out of the overlay until it is the size you want. Ideally, the golden outline will be the same size as the red lines in the paragon board. The location of the overlay is automatically saved.

**Tips**

- Overlays may not work in exclusive fullscreen; use **borderless windowed** if the overlay does not appear.
- Planner websites can change over time. If an import/export stops working, please report a bug.

## Info Panel Overlay

The following images are historical upstream English UI examples. Current menu labels and appearance may differ.

![Upstream information panel, vertical](assets/readme/infopanel_vert.png)
![Upstream information panel, horizontal](assets/readme/infopanel_hort.png)

The Info Panel provides real-time tracking for World Events and session-based statistics for Gold and Experience.

**How to use**

1. Toggle the overlay using the hotkey (default **F6**, configurable in *Advanced options*).
1. **Move**: Click and drag the overlay to your preferred location.
1. **Settings**: Right-click anywhere on the overlay to open the context menu.
1. **Lock**: Once positioned, select **Lock Position** from the right-click menu to prevent accidental movement.

![Upstream English information panel menu](assets/readme/infopanel_menu.png)

**Features and Settings (Right-Click Menu)**

- **Visibility Toggles**: Directly enable/disable the display of **World Boss**, **Legion**, and **Helltide** timers.
- **Timers**:
  - Timers automatically sync with [Helltides.com](https://helltides.com).
  - **World Boss & Legion**: Countdowns are green, flashing orange in the last 5 minutes.
  - **Helltide**:
    - When active, the timer is yellow, flashing orange in the last 5 minutes.
    - The break period before the next Helltide is green, flashing orange in the last 1 minute.
- **Gold Config (Submenu)**:
  - **Track Gold**: Master toggle to enable/disable gold tracking. When disabled, other gold-related options are grayed out.
  - **Show Gold Per Hour**: Displays your calculated Gold Per Hour for the current session.
  - **Show Gold Gained**: Shows total gold accumulated since the last reset.
- **Exp Config (Submenu)**:
  - **Track Exp**: Master toggle to enable/disable experience tracking. When disabled, other exp-related options are grayed out.
  - **Show EXP Per Hour**: Displays your calculated Experience Per Hour.
  - **Show EXP Gained**: Shows total experience accumulated since the last reset.
  - **Show Time to Level**: Estimated time remaining until your next level based on current EPH.
  - **Show Next Scan**: Shows the remaining cooldown until the next automatic experience check.
  - **Auto Capture EXP When Inventory Opened**: If enabled, the tool will automatically hover your experience bar to scan values whenever you open your inventory.
  - **EXP Capture Time (Submenu)**: Set the cooldown interval (e.g., Never, 0m, 3m) for automatic scans.
  - **Configure EXP Bar Position**: Calibrate the tool by dragging a box over your experience bar on screen.
  - **Reset EXP Bar Position**: Resets the custom EXP bar position to default.
- **Reset Stats (Submenu)**:
  - **Reset Gold**: Clears current session gold data and sets a new baseline.
  - **Reset Exp**: Clears current session experience data.
- **UI Adjustments**:
  - **Orientation**: Switch between **Horizontal** and **Vertical** layouts.
  - **Increase/Decrease Size**: Adjust the font size and overall scale of the overlay.
- **Font (Submenu)**:
  - Select your preferred font family for the overlay text.
- **System**:
  - **Refresh Timers Now**: Manually force a refresh of event data from the web.
  - **Lock Position**: Disables dragging to keep the overlay static.
  - **Close Overlay**: Closes the Info Panel Overlay.

**Exp Bar Position Suggestion**
Configure exp bar position as shown here. This position seems to work the best for easy data captures.
![Upstream English client experience bar example](assets/readme/infopanel_expbar.png)

**Tracking Logic**

- The overlay captures data via the game's Text-to-Speech (TTS) system.
- **Gold Tracking**:
  - To initialize, turn on track gold and open inventory.
  - Includes verification logic to ignore transient "Sell Value" tooltips from items.
- **Experience Tracking**:
  - To initialize, simply hover over your experience bar in-game.
  - **Automatic Scanning**: If "Inv Open (Capture EXP)" is enabled in settings, the overlay will automatically move your mouse over the experience bar to scan for updates whenever you open your inventory.
  - **Cooldown**: The "EXP Capture Time" setting controls how frequently these automatic scans occur, preventing excessive mouse movements.

## Reporting problems

See [LICENSE](LICENSE) for licensing. Use
[GitHub Issues](https://github.com/ytwytw/d4lf/issues) for bug reports and improvements.
