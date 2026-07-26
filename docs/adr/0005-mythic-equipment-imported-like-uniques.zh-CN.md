# 神话装备的导入与过滤方式与暗金装备完全一致

**简体中文** | [English](0005-mythic-equipment-imported-like-uniques.md)

神话装备（Mythic）此前是完全独立的一类物品，因此每个构筑指南导入器（maxroll、d4builds、mobalytics、infinitybuilds）都对它们做特殊处理：神话装备物品的词缀被丢弃，其名称被塞进一个 `mythic_names` 列表，整个流水线把所有神话装备堆进一个笼统的 `"Mythics"` `ItemFilterModel` 中——`item_type` 为空、没有 `affix_pool`——仅按名称匹配，且跨所有物品类型。在当前版本中，神话装备在机制上就是一个稀有度值不同（紫色）的暗金装备：同样只有一个独特威能，同样只有少数常规词缀。过滤引擎（`_check_unique_aspects_for_item`、`_check_affixes`）已经将 `ItemRarity.Mythic` 和 `ItemRarity.Unique` 一视同仁，因此这种堆放纯粹是导入器侧的历史遗留，而且它产出的配置文件严格劣于将神话装备当作暗金装备处理：没有 `item_type`、没有词缀匹配，只有一个名称。

## 决定

对于装备，所有导入器现在将 `rarity in (unique, mythic)` 视为同一种情况：根据物品名称赋 `unique_aspect`，正常解析 `item_type`，并用解析出的词缀构建 `affix_pool`/`inherent_pool`，`minCount=1`（与暗金相同）。`mythic_names` 列表、`Variant.mythic_names` 字段以及 `add_mythics_to_filters`/`"Mythics"` 桶被彻底移除。如果某个具名暗金/神话物品未能解析出任何词缀，该物品仍会被保留（仅按 `unique_aspect` 匹配），而不是被静默丢弃——这一点此前已适用于印记/护身符（seal/charm）导入，现在统一适用于装备。

这一等价关系仅限于**装备**。印记、护身符、贡品和符印保留其现有的、独立的神话处理逻辑（例如 `filter.py` 中"无论是否匹配都始终保留神话印记/护身符/贡品"的回退），不受本次变更影响。`should_keep()` 中既有的装备"始终保留每个神话装备"回退同样不受影响：由于会先尝试正常的词缀匹配，它现在只在导入的（或手写的）词缀过滤器确实不匹配时充当安全网。

## 影响

- 由构筑指南生成的配置文件现在按神话装备的实际属性过滤，而不再只按名称过滤，与暗金装备的既有行为一致。
- infinitybuilds.py 需要做一点顺序调整：它在一个共享循环中解析装备和印记/护身符物品，因此神话分支必须移到与现有 unique-vs-non-unique 逻辑并行运行（而非在其之前），而不是提前短路。
- 已包含此前导入产生的 `"Mythics"` 分节的旧配置文件仍可正常加载并照常工作——`ProfileModel` 不关心分节名称，只关心内容。
