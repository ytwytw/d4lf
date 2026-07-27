# 领域文档

[English](domain.md)

工程技能在浏览代码库时应按以下方式使用领域文档。

## 开始浏览前

- 阅读仓库根目录的 **`CONTEXT.md`**；或者
- 如果根目录存在 **`CONTEXT-MAP.md`**，按其中索引阅读与主题相关的各个 `CONTEXT.md`。
- 阅读 **`docs/adr/`** 中与准备修改区域相关的 ADR。多上下文仓库还应检查 `src/<context>/docs/adr/`。

这些文件不存在时应**直接继续**，不要报告缺失，也不要预先建议创建。`/domain-modeling`
技能（由 `/grill-with-docs` 和 `/improve-codebase-architecture` 进入）只在术语或决策真正
明确后按需创建这些文件。

## 文件结构

单上下文仓库：

```text
/
|-- CONTEXT.md
|-- docs/adr/
|   |-- 0001-event-sourced-orders.md
|   `-- 0002-postgres-for-write-model.md
`-- src/
```

## 使用词汇表中的术语

输出中命名领域概念时，例如 Issue 标题、重构提案、假设或测试名，应使用 `CONTEXT.md`
定义的术语，不要改用词汇表明确排除的同义词。

如果词汇表没有所需概念，要么正在引入项目未使用的语言，应重新考虑；要么确实存在缺口，
应记录给 `/domain-modeling`。

## 标明与 ADR 的冲突

如果输出与现有 ADR 冲突，应明确指出，不要静默覆盖：

> 与 ADR-0007（事件溯源订单）冲突，但值得重新讨论，因为……
