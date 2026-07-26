# Simplified Chinese Translation Evidence Audit

[简体中文](zhcn-translation-audit.md) | **English**

This page records the review criteria for the zhCN aggregated data and the candidates still awaiting verification. It does not treat any third-party database as ground truth; instead, it ensures that every manual override can be traced back to reviewable objects and evidence.

## Review criteria

Evidence is used in the following order:

1. Blizzard China official announcements, patch notes, and in-game footage from the Simplified Chinese client.
1. Paired data in which English and Simplified Chinese share the same SNO/object ID.
1. Cross-checking of object-level translations against another independent database, in-game screenshot, or reference page.
1. Only results that are semantically identical with an unambiguous object identity may enter `reviewed_zhCN.json`.

D2Core is one of the aggregation sources, not a source of truth. Missing data in D2Core must not disable existing Chinese text. InfinityBuild's machine translations are not accepted as evidence and do not factor into review conclusions.

The source versions pinned for this round are:

- d4data `3.1.1.72836`
- D2Core `72698`
- Diablo4Companion `3.1.1.72903` at [data commit `6e52cac`](https://github.com/josdemmers/Diablo4Companion/commit/6e52cac060a5eed18411ba2f70c99a35e765d7cd)

Mismatched source versions will continue to block the release gate from passing automatically.

## Results of this round

After re-auditing the initial 130 unresolved records:

- 36 records were fixed by same-SNO numeric template matching.
- 4 records were fixed via D2Core multiplier aliases.
- 22 `_GURTEST` internal test records were removed from the official source scope.
- The remaining records were handled through object-level evidence, official terminology, or conflict corrections.
- 18 unresolved records remain: 2 material drop rates, 1 current-season sigil description, and 15 tributes.

The current resolved set contains no translation conflicts, alias collisions, or official entries excluded due to missing historical snapshots.

Numeric template fallback is used only to establish object identity. Output aliases strip the numeric values from source instances, so that a value observed once is not mistaken for fixed text applying to all gear; numbers in exact-text matches are unaffected.

The generator automatically excludes objects by the `_GURTEST` suffix in d4data internal names; in this round, the AffixFamily and empty gameplay metadata of the 22 current objects were additionally reviewed manually. This judgment does not depend on whether D2Core includes them. See a [current object example](https://github.com/DiabloTools/d4data/blob/5b68e74dc0a54f03cce81e0591a3a29a48a1a694/json/base/meta/Affix/Talisman_SealAffix_Legendary_Druid_Wolf_03_GURTEST.aff.json) for review.

## Newly approved tributes

| stable ID                        | 简体中文         | Cross-evidence                                                                                                                                                               |
| -------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tribute_of_ascendance_resolute` | 晋升贡品（决绝） | [Wowhead object 2090362](https://www.wowhead.com/diablo-4/cn/item/x-2090362), [zhCN client screenshot](https://bubaigei.com/wp-content/uploads/2024/10/2024101402390557.png) |
| `tribute_of_harmony`             | 和谐供品         | [Wowhead object 2125691](https://www.wowhead.com/diablo-4/cn/item/x-2125691), [zhCN client screenshot](https://bubaigei.com/wp-content/uploads/2024/10/2024101402390862.png) |
| `tribute_of_radiance_resolute`   | 光辉贡品（决绝） | [Wowhead object 2077998](https://www.wowhead.com/diablo-4/cn/item/x-2077998), [zhCN client screenshot](https://bubaigei.com/wp-content/uploads/2024/10/2024101402390862.png) |
| `tribute_of_titans`              | 巨人贡品         | [Wowhead object 2090358](https://www.wowhead.com/diablo-4/cn/item/x-2090358), [independent reference](https://news.17173.com/content/01272025/151203334.shtml)               |

Within the Harmony series, the character "供" in `和谐供品` applies only to object `2125691`. Subsequent objects `Lesser/Greater Tribute of Harmony` use "贡品" in the data, so no global replacement may be made.

## Retained candidates

The following results have only a single public zhCN object source, or still have version conflicts, and are therefore not written into the reviewed overrides:

- Two `crafting_material_drop_rate` records: the candidates for objects [2547993](https://www.wowhead.com/diablo-4/cn/affix/of-the-artisan-2547993) and [2593576](https://www.wowhead.com/diablo-4/cn/affix/artisanal-2593576) are both "制作材料掉率", but a second independent zhCN data source is missing.
- `sigils:positive:ruptures`: "混沌裂隙" and "丧钟密室" are officially confirmed, but no complete client entry has been found.
- The remaining 14 tribute variants: Wowhead has exact object ID candidates, but there is no second object-level zhCN source.
- `tribute_of_heritage`: the zhCN object page incorrectly shares the name "巨人贡品" with `tribute_of_titans`; the Traditional Chinese candidate is "傳承貢品", which cannot be used to infer the official Simplified Chinese term.

Official terminology references:

- [Season of Hatred Rising: Chaos Rifts and Knell Vault](https://d4.blizzard.cn/news/24268702/index.html)
- [China server patch notes](https://d4.blizzard.cn/news/24287406/)
- [Official tribute translation reference](https://d4.blizzard.cn/news/24244466/index.html)
