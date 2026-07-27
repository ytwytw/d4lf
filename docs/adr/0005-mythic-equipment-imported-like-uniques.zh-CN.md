# 神话装备与暗金装备采用完全相同的导入和过滤方式

[English](0005-mythic-equipment-imported-like-uniques.md)

神话装备过去被视为完全独立的物品类型，因此每个 Build 导入器（Maxroll、D4Builds、
Mobalytics、InfinityBuilds）都进行特殊处理：丢弃神话装备词缀，把名称放入
`mythic_names` 列表，再把所有物品合并到一个 `"Mythics"` `ItemFilterModel` 中。该模型
没有 `item_type` 和 `affix_pool`，只能跨所有物品类型按名称匹配。

在当前游戏中，神话装备在机制上就是具有不同紫色稀有度的暗金装备：同样具有一个暗金特效和
若干普通词缀。过滤引擎已经对 `ItemRarity.Mythic` 与 `ItemRarity.Unique` 使用相同逻辑，
因此旧行为只是导入器的历史遗留，而且生成的 Profile 信息更少。

## 决策

对于装备，所有导入器统一处理 `rarity in (unique, mythic)`：从物品名称设置
`unique_aspect`，正常解析 `item_type`，并从词缀建立 `affix_pool`/`inherent_pool`，
`minCount=1`。删除 `mythic_names`、`Variant.mythic_names`、`add_mythics_to_filters` 和
`"Mythics"` 汇总区。即使具名暗金或神话装备没有解析出词缀，仍按 `unique_aspect` 保留，
不会静默丢弃。

这一等价关系只适用于**装备**。典籍、淬炼手册、贡品和钥匙继续使用各自的神话处理逻辑。
装备过滤中原有的“始终保留神话”兜底也保持不变。

## 影响

- 从 Build 指南生成的 Profile 会按神话装备的实际属性过滤，而不再只看名称。
- InfinityBuilds 会在共享循环中解析装备及其他物品，因此需要调整神话分支顺序，使其与现有暗金/非暗金逻辑并列。
- 旧 Profile 中已有的 `"Mythics"` 区段仍可正常加载；`ProfileModel` 只关心内容，不依赖区段名。
