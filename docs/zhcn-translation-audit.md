# 简体中文翻译证据审计

本页记录 zhCN 聚合数据的审核口径和仍待验证的候选。它不是把某个第三方数据库当作真值，而是让每条人工覆盖都能回到可复查的对象和证据。

## 审核口径

证据按以下顺序使用：

1. 暴雪国服公告、补丁说明和简中客户端实机画面。
1. 英文与简中使用相同 SNO/对象 ID 的成对数据。
1. 另一独立数据库、实机截图或资料页对对象级译名的复核。
1. 只有语义相同且对象身份明确的结果才能进入 `reviewed_zhCN.json`。

D2Core 是聚合来源之一，不是 source of truth。D2Core 缺失不能禁用已有中文。InfinityBuild 的机器翻译不作为证据，也不参与审核结论。

本轮固定的源版本为：

- d4data `3.1.1.72836`
- D2Core `72698`
- Diablo4Companion `3.1.1.72903` at [data commit `6e52cac`](https://github.com/josdemmers/Diablo4Companion/commit/6e52cac060a5eed18411ba2f70c99a35e765d7cd)

源版本不一致会继续阻止发布门禁自动通过。

## 本轮结果

最初的 130 条未解析记录经重新审计后：

- 36 条由同 SNO 数字模板匹配修复。
- 4 条由 D2Core multiplier 别名修复。
- 22 条 `_GURTEST` 内部测试记录从正式源范围移除。
- 其余记录通过对象级证据、官方术语或冲突修正处理。
- 当前剩余 18 条 unresolved：2 条材料掉率、1 条当季符印说明、15 条贡品。

当前已解析集合没有翻译冲突、别名碰撞或因历史快照缺失而排除的正式词条。

数字模板回退只用于建立对象身份。输出别名会移除来源实例中的数值，避免把某次取值误当成所有装备都适用的固定文本；精确文本命中的数字不受影响。

生成器按 d4data 对象内部名称的 `_GURTEST` 后缀自动排除；本轮另对 22 个当前对象的 AffixFamily 和空 gameplay 元数据做了人工复核。该判断不依赖 D2Core 是否收录。可复查[当前对象示例](https://github.com/DiabloTools/d4data/blob/5b68e74dc0a54f03cce81e0591a3a29a48a1a694/json/base/meta/Affix/Talisman_SealAffix_Legendary_Druid_Wolf_03_GURTEST.aff.json)。

## 新批准贡品

| stable ID                        | 简体中文         | 交叉证据                                                                                                                                                           |
| -------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tribute_of_ascendance_resolute` | 晋升贡品（决绝） | [Wowhead 对象 2090362](https://www.wowhead.com/diablo-4/cn/item/x-2090362)、[简中客户端截图](https://bubaigei.com/wp-content/uploads/2024/10/2024101402390557.png) |
| `tribute_of_harmony`             | 和谐供品         | [Wowhead 对象 2125691](https://www.wowhead.com/diablo-4/cn/item/x-2125691)、[简中客户端截图](https://bubaigei.com/wp-content/uploads/2024/10/2024101402390862.png) |
| `tribute_of_radiance_resolute`   | 光辉贡品（决绝） | [Wowhead 对象 2077998](https://www.wowhead.com/diablo-4/cn/item/x-2077998)、[简中客户端截图](https://bubaigei.com/wp-content/uploads/2024/10/2024101402390862.png) |
| `tribute_of_titans`              | 巨人贡品         | [Wowhead 对象 2090358](https://www.wowhead.com/diablo-4/cn/item/x-2090358)、[独立资料](https://news.17173.com/content/01272025/151203334.shtml)                    |

在 Harmony 系列中，`和谐供品` 的“供”只适用于对象 `2125691`。后续对象 `Lesser/Greater Tribute of Harmony` 的数据使用“贡品”，不能做全局替换。

## 保留候选

下列结果只有一个公开简中对象源，或仍有版本冲突，因此不会写入受审覆盖：

- `crafting_material_drop_rate` 两条记录：对象 [2547993](https://www.wowhead.com/diablo-4/cn/affix/of-the-artisan-2547993) 和 [2593576](https://www.wowhead.com/diablo-4/cn/affix/artisanal-2593576) 的候选均为“制作材料掉率”，但缺少第二个独立简中数据源。
- `sigils:positive:ruptures`：官方已确认“混沌裂隙”和“丧钟密室”，但没有找到完整客户端词条。
- 其余 14 个贡品变体：Wowhead 有精确对象 ID 候选，但没有第二个对象级简中来源。
- `tribute_of_heritage`：简中对象页错误地与 `tribute_of_titans` 同名为“巨人贡品”；繁中候选为“傳承貢品”，不能据此推断正式简中。

官方术语参考：

- [苏醒赛季：混沌裂隙与丧钟密室](https://d4.blizzard.cn/news/24268702/index.html)
- [国服补丁说明](https://d4.blizzard.cn/news/24287406/)
- [贡品官方译名参考](https://d4.blizzard.cn/news/24244466/index.html)
