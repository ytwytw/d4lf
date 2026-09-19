# 第 15 赛季中文解析与发布缺口复核

> 2026-09-19 增量更正：本机已确认并修复 `lesser_tribute_of_harmony` → 次级和谐贡品，
> 当前未确认贡品为 12 项，“恶毒”名称歧义仍未解除。以下 13 项清单保留为原审查快照；
> 最新来源与限定测试见 [9 月 19 日核验报告](season15-zhcn-upstream-20260919.md)。上游 `v10.0.4` 尚未合入。

本次复核以 `v10.0.3` 英文目录、构建 `3.2.1.73552` 的锁定来源以及本机中文客户端为边界。
通过三个实机样本不代表整个目录已具备无人值守发布条件。

## 已修复

- 中文套装名称现在解析为稳定 ID；此前中文显示名被直接与英文 ID 比较，套装规则无法命中。
- 法典升级与新外观标记使用已有中英文语法数据，不再只识别英文提示。
- 中文贡品无需在稀有度和名称之间插入空格；帧切分不再把稀有度行误当作物品名称。
- 补齐英文目录原本仅存在于枚举中的神符、赫拉迪姆封印、贡品类型，中文别名随之纳入可审计目录。
- 封印的神符槽位行被识别为固有属性，不被误标为强效词缀。
- 本机稀有封印的固定 `+1 至所有技能` 精通没有强效星标；结合锁定 D2Core 的固定值记录，
  不再仅因缺少数值范围就把这条固定值精通误算成强效词缀。
- 神符与原装备共享暗金 ID 时，不再继承原装备的固有属性数量。例如英文源数据中的祖父神符
  `Talisman_Charm_Unique_2HSword_Unique_Generic_001.itm.json` 没有固有属性，而双手剑有一条。
- 修正整数范围与小数实际值混用时的截断：`10.5 [8 - 12]` 必须为 `10.5`，不是 `5`。
- 未知或歧义威能、未知套装、未知符印词条与贡品，以及缺少强度、词缀或威能的装备片段，现在报解析失败，
  不再生成看似完整、可被标记为垃圾的物品。传奇封印没有普通传奇威能的合法形态保持支持。
- 共享正则与文本边界移到独立模块，解除解析组装模块与细节模块的循环引用；生成器的 Power 索引逻辑也独立成辅助函数，
  保留 CoreTOC 优先、文件扫描后备，符合每文件 300 行限制。
- 修复清单中八条文本被替换成问号、与真实运行时译文不符的来源记录；新增逐条文本和翻译哈希一致性检查。

## 新增译名的证据

| 稳定 ID / 语法                                                                      | 采用文本           | 证据                                                                         |
| ----------------------------------------------------------------------------------- | ------------------ | ---------------------------------------------------------------------------- |
| `item_types:Charm`                                                                  | 神符               | 暴雪“憎恨之王”说明明确区分护身符系统和其中的神符物品。                       |
| `item_types:HoradricSeal`                                                           | 赫拉迪姆封印       | 暴雪 3.1 补丁说明包含完整物品类型。                                          |
| `item_types:Tribute`                                                                | 贡品               | 暴雪 3.2.1 补丁说明使用此类别名称。                                          |
| `tributes:greater_tribute_of_refinement`                                            | 强效精炼贡品       | 暴雪同一篇 3.2.1 英/中文补丁的幽暗之城奖励修正逐项对应。                     |
| `tributes:tribute_of_ingenuity`                                                     | 巧思贡品           | 暴雪同一篇英/中文补丁的高级搜索修正逐项对应。                                |
| 神符槽位语法                                                                        | 神符插槽、神符槽位 | 前者见暴雪系统说明；后者由本机本季稀有封印提示截图确认。                     |
| `affixes:crafting_material_drop_rate`、`charms_affixes:crafting_material_drop_rate` | 制作材料掉率       | 本机 3.2.1.73552 中文客户端实际神符 TTS：`+2.2% 制作材料掉率 [1.9 - 2.8]%`。 |
| `sigils:positive:ruptures`                                                          | 混沌裂隙           | 暴雪英/中文赛季公告的丧钟密室章节逐项对应；仅确认名称，不编造完整词条描述。  |

来源：[憎恨之王中文说明](https://d4.blizzard.cn/news/24267729/)、
[3.1 中文补丁](https://d4.blizzard.cn/news/24287406/)、
[3.2.1 中文补丁](https://d4.blizzard.cn/news/24295394/)、
[同篇英文补丁](https://news.blizzard.com/en-us/article/24295394/)、
[混沌裂隙中文公告](https://d4.blizzard.cn/news/24268702/index.html)、
[同篇英文公告](https://news.blizzard.com/en-us/article/24268702/hunt-the-death-cult-in-season-of-death-awakening)。
新增翻译保存于 reviewed overrides 和 locale manifest，并记录文本哈希及引用地址。
实机封印、套装神符和两枚稀有神符的原始文本保存在
`tests/perception/data/zhcn_live_talisman.json`；断言包含类别、强度、套装、固有属性、词缀数值及强效分类。

## 尚未补齐，禁止声称完整支持

现有锁定的 D2Core 英/简中配对快照与 Diablo4Companion 数据未提供下列键的可靠配对文本。
复查暴雪中文公告后补齐了上表两个贡品，但尚未找到下列项目的精确官方译名；不会由相邻名称推导“强效/次级”等前缀。

```text
tributes:greater_tribute_of_armaments
tributes:greater_tribute_of_harmony
tributes:greater_tribute_of_ingenuity
tributes:greater_tribute_of_the_horadrim
tributes:lesser_tribute
tributes:lesser_tribute_of_harmony
tributes:lesser_tribute_of_ingenuity
tributes:lesser_tribute_of_the_horadrim
tributes:major_tribute_of_andariel
tributes:minor_tribute_of_andariel
tributes:tribute_of_andariel
tributes:tribute_of_heritage
tributes:tribute_of_the_horadrim
```

另有 `malicious` 与 `virulent` 同为“恶毒”的历史/当前目录冲突。旧代码按字母顺序选中一个 ID，不能证明二者同义。
现改为拒绝歧义中文输入；英文稳定 ID 仍可分别精确解析。需游戏威能文本与稳定 ID 的可验证对应后才能增加消歧规则。

`manifest.json` 与 `quality-report.json` 已撤销原先过度乐观的 `runtime_ready=true`。
2026-09-19 更新后可进行有边界的本地测试，但公开完整中文无人值守发行仍须补齐剩余 12 个贡品记录、消除上述歧义并重新跑发布门禁。
这里列出的类型/词缀组合单元测试是基于已确认词汇构造的回归案例；只有实机 smoke 文档明确记录的样本才算客户端验收。
