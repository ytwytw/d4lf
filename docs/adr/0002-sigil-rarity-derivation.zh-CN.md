# 符印稀有度由 sigils.json 的 rarities 映射推导

**简体中文** | [English](0002-sigil-rarity-derivation.md)

Diablo 4 不会在符印对象上暴露稀有度，因此用于过滤的符印稀有度是推导出来的：扫描符印的词缀（`item.affixes + item.inherent`），在 `sigils.json["rarities"]` 中找到的第一个词缀决定其稀有度。当没有任何词缀能解析出稀有度时，该符印的稀有度为未知。

非空的符印 `rarity` 过滤器会作为 AND 门，在既有的黑名单/白名单逻辑之前应用。未知稀有度按失败关闭（fail-closed）处理：它永远不匹配非空的稀有度过滤器，因此该符印会被丢弃，并以 debug 级别记录未解析的查找，以暴露映射中的缺口。

## 影响

- `sigils.json` 中的 `rarities` 映射（此前未被使用）变为关键路径；其中的缺口会导致在启用稀有度过滤器时，本应保留的符印被过滤掉。
- 选择失败关闭而非失败开放（fail-open），是为了让 `rarity: [rare]` 过滤器不会悄悄放行未知稀有度的符印；debug 日志是对映射覆盖不全的缓解措施。
