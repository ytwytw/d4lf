# 贡品过滤器采用单对象语义，名称与稀有度之间为 OR 关系

**简体中文** | [English](0006-tribute-filter-single-object-and-semantics.md)

`Tributes:` 接受一个包含 `name` 列表和 `rarity` 列表的对象。当贡品的名称在 `name` 列表中
**或**其稀有度在 `rarity` 列表中时，该贡品被保留。省略某个键意味着
不评估该维度。`Tributes: {}`（两个列表都为空）不保留任何贡品。

只有完全省略 `Tributes:` 键才表示"保留所有贡品"。

如果配置文件使用旧的列表形态 `Tributes:`，则每个列表项中的所有名称和稀有度
会在加载时合并为一个对象（迁移是静默的）。

## 考虑过的选项

- **名称与稀有度之间为 OR** —— 已采用：符合用户预期，即 `name: [harmony], rarity: [legendary]`
  保留任意稀有度的 tribute_of_harmony **以及**任意名称的所有传奇贡品。与
  符印黑名单/白名单的工作方式一致（每个列表内部为 OR，不同列表是独立的门）。
- **名称与稀有度之间为 AND** —— 已否决：`name: [harmony], rarity: [legendary]` 将只保留
  同时为传奇的 harmony 贡品，静默丢弃非传奇的 harmony 贡品和
  非 harmony 的传奇贡品，这既出人意料又难以理解。
- **同时支持单对象和对象列表** —— 已否决：为单对象 OR 语义已覆盖的 OR 模式
  增加永久性的 schema 复杂度。

## 影响

- `ProfileModel.tributes` 为 `TributeFilterModel | None`。
- 使用列表形态 `Tributes:` 的现有配置文件会被静默迁移；无需手动编辑。
- 配置文件编辑器只需处理一个扁平的 name + rarity 模型。
- `Tributes: {}`（空）不保留任何贡品；只有缺失该键才保留所有贡品。
