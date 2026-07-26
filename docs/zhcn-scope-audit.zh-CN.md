# 针对《暗黑破坏神 IV》3.1 的 zhCN 范围审计

**简体中文** | [English](zhcn-scope-audit.md)

这份来源快照说明将当前装备过滤需求与历史解析器类型以及 D4LF 的可选非装备过滤器区分开来。

## 权威产品范围

暴雪的 Lord of Hatred 拾取过滤器文档说明，游戏内置过滤器适用于掉落、背包、储物箱和商人中的装备。
它明确排除非装备物品，如 Temper 手册、材料（reagents）、宝石和货币。其装备条件包括物品类型、
稀有度、物品强度、词缀、Codex 升级、特定暗金（Uniques）和护符装备套装加成。

来源：

- <https://news.blizzard.com/en-us/article/24267729/prepare-for-the-reckoning-lord-of-hatred-draws-near>
- <https://news.blizzard.com/en-us/article/24287406/diablo-iv-patch-notes>
- <https://news.blizzard.com/en-gb/article/24271857/diablo-iv-patch-notes-3-0>

3.0 说明确认梦魇地下城符印仍然有效。3.1 说明确认护符装备、印记和护身符仍然有效，并明确通过
将现有副本转换为“金色顿悟封印”来移除“断指封印”。

## D4LF 代码路径

- 装备过滤支持护甲、武器、首饰、词缀、威能、暗金、印记和护身符。
- 符印和贡品在普通装备规则之外有显式的可选过滤部分。
- 药剂、熏香、材料和 Temper 手册在配置文件过滤之前就被忽略。
- `Tome.itt` 没有装备槽位，也没有武器类别。当前唯一引用它的物品是 `SkillPointTome.itm`。实际
  可装备的书本样式副手是 `FocusBookOffHand`，显示为 `Focus`。

因此，`Tome` 在 D4LF 中被归类为非装备消耗品，而不是武器。

## 外部来源评估

### Diablo4Companion

公开的配对 `enUS`/`zhCN` 记录仍是最佳的无人值守本地化输入，因为它们带有共享的游戏身份。其物品
类型数据已经为 `Nightmare Sigil` 提供了中文标签；生成器现在通过共享的 `Type=sigil` 身份而不是
旧的 `custom type sigil` 占位符来关联。

仓库：<https://github.com/josdemmers/Diablo4Companion>

### Maxroll

Maxroll 可用于检查哪些装备、词缀、威能和暗金出现在活跃 build 中。现有 D4LF 导入器测试已覆盖
第 14 赛季指南 URL 和 Maxroll 的第 14 赛季 planner 负载。它不是稳定的中文本地化来源，且在此
环境中直接自动访问页面受 robots 限制。

站点：<https://maxroll.gg/d4/>

### InfinityBuilds / InfinityTools

InfinityTools 将装备、词缀、威能和暗金与符印、Tempering、材料、消耗品以及诸如 tome 之类的其他
物品分开。该分类独立支持装备/非装备边界。其公开 build 数据 API 已被 D4LF 的导入器使用，但该站点
将其当前 build 集合标注为第 13 赛季，而官方和 D2Core 页面已是第 14 赛季，因此它是交叉核对而非
赛季权威。

站点：

- <https://infinitybuilds.gg/en/builds>
- <https://tools.infinitybuilds.gg/en/database>

### D2Core

检查时，D2Core 的公开 build 列表对 `S14` 是最新的，并显示全部八个当前职业。D4LF 将 D2Core 的
公开静态数据库文件用作补充中文来源，不自动化也不绕过其交互式 planner。D2Core 不定义目录成员
资格：当其快照中缺少某条记录时，只要另一个配对来源提供中文文本，该记录仍保持启用。项目所有者
已确认在 README 署名的情况下直接使用和公开再分发。该有界快照在 build `72698` 包含 1,008 条词缀、
363 条威能、295 条暗金和 804 条扁平化护符装备（Talisman）记录的配对 `enUS`/`zhCN` 记录。护符装备覆盖包括
365 个护身符、11 枚印记、45 个套装、110 条护身符词缀和 273 条印记词缀。每个文件都有版本和
哈希，每个语言配对在生成前都通过 `(key, id)` 验证。

署名和机器可读发布状态记录在 `docs/third-party-data.md` 中，并由公开导出门槛强制执行。

站点：<https://www.d2core.com/>

## 交付层级

1. 核心装备：护甲、武器、首饰、物品标题、词缀、威能、暗金和神话。
1. 护符装备：印记、护身符、它们的词缀，以及面向 Lord of Hatred 拥有者的套装加成。
1. D4LF 扩展：梦魇/escalation 符印和贡品。

药剂、熏香、材料、Temper 手册、tome、宝箱、宝石、符文和货币在 zhCN 装备里程碑之外。它们不得
阻碍装备就绪，也不得产生客户端采集工作。
