# Issue 追踪器：本地 Markdown

**简体中文** | [English](issue-tracker.md)

本仓库的 issue 和 PRD 以 markdown 文件形式存放在 `.scratch/` 中。

## 约定

- 每个特性一个目录：`.scratch/<feature-slug>/`
- PRD 为 `.scratch/<feature-slug>/PRD.md`
- 实现 issue 为 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 开始编号
- 分诊状态记录为每个 issue 文件顶部附近的一行 `Status:`（角色字符串见 `triage-labels.md`）
- 评论和对话历史追加到文件底部的 `## Comments` 标题之下

## 当技能说"发布到 issue 追踪器"时

在 `.scratch/<feature-slug>/` 下创建一个新文件（如需要则先创建目录）。

## 当技能说"获取相关工单"时

读取所引用路径处的文件。用户通常会直接给出路径或 issue 编号。

## Wayfinding 操作

由 `/wayfinder` 使用。**map** 是一个文件，每个工单对应一个 **child** 文件。

- **Map**：`.scratch/<effort>/map.md` —— Notes / Decisions-so-far / Fog 正文。
- **Child 工单**：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 开始编号，问题写在正文中。一行 `Type:` 记录工单类型（`research`/`prototype`/`grilling`/`task`）；一行 `Status:` 记录 `claimed`/`resolved`。
- **阻塞**：顶部附近的一行 `Blocked by: NN, NN`。当其列出的每个文件都是 `resolved` 时，工单解除阻塞。
- **前沿**：扫描 `.scratch/<effort>/issues/` 中处于打开、未阻塞且未被认领的文件；编号最小者优先。
- **认领**：在任何工作开始之前，设置 `Status: claimed` 并保存。
- **解决**：在 `## Answer` 标题下追加答案，设置 `Status: resolved`，然后在 `map.md` 的 Decisions-so-far 中追加一条上下文指针（要点 + 链接）。
