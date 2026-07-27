# 贡品过滤器采用单对象结构，名称与稀有度之间使用 OR 语义

[English](0005-tribute-filter-single-object-and-semantics.md)

`Tributes:` 接受一个包含 `name` 列表和 `rarity` 列表的对象。贡品名称在 `name` 列表中，
**或**稀有度在 `rarity` 列表中时即保留。省略某个键表示不评估该维度。
`Tributes: {}` 中两个列表都为空，因此不保留任何贡品。

只有完全没有 `Tributes:` 键才表示“保留所有贡品”。

如果 Profile 使用旧的列表结构 `Tributes:`，加载时会把所有列表项中的名称和稀有度静默
合并到一个对象。

## 考虑过的方案

- **名称与稀有度之间使用 OR**：采用。`name: [harmony], rarity: [legendary]` 会保留任意稀有度的 harmony 贡品，以及任意名称的传奇贡品，符合用户预期。
- **名称与稀有度之间使用 AND**：拒绝。它只会保留同时满足两项的贡品，容易意外丢弃物品。
- **同时支持单对象和对象列表**：拒绝。单对象的 OR 语义已经覆盖需求，双结构只会永久增加 Schema 复杂度。

## 影响

- `ProfileModel.tributes` 为 `TributeFilterModel | None`。
- 旧列表结构会静默迁移，不需要手动编辑。
- Profile 编辑器只需处理一个扁平的名称与稀有度模型。
- 空的 `Tributes: {}` 不保留任何贡品；只有缺少该键才保留全部。
