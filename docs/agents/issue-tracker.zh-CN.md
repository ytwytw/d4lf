# Issue 跟踪：本地 Markdown

[English](issue-tracker.md)

本仓库的 Issue 和 PRD 以 Markdown 文件存放在 `.scratch/` 中。

## 约定

- 每个功能一个目录：`.scratch/<feature-slug>/`
- PRD 路径：`.scratch/<feature-slug>/PRD.md`
- 实现 Issue 路径：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 编号
- 分流状态记录在每个 Issue 文件顶部附近的 `Status:` 行中，角色字符串见 `triage-labels.md`
- 评论和对话历史追加在文件底部的 `## Comments` 标题下

## 技能要求“发布到 Issue 跟踪器”时

在 `.scratch/<feature-slug>/` 下创建文件，必要时同时创建目录。

## 技能要求“获取相关工单”时

读取所引用路径的文件。用户通常会直接提供路径或 Issue 编号。

## Wayfinding 操作

供 `/wayfinder` 使用。**Map** 是每个工单对应一个**子文件**的索引文件。

- **Map**：`.scratch/<effort>/map.md`，包含 Notes、Decisions-so-far 和 Fog。
- **子工单**：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 编号，正文写明问题。`Type:` 为 `research`/`prototype`/`grilling`/`task`，`Status:` 为 `claimed`/`resolved`。
- **阻塞**：顶部附近使用 `Blocked by: NN, NN`。列出的文件全部为 `resolved` 后，工单解除阻塞。
- **Frontier**：扫描 `.scratch/<effort>/issues/`，查找开放、未阻塞且无人认领的文件，编号最小者优先。
- **认领**：开始工作前把 `Status:` 改为 `claimed` 并保存。
- **解决**：在 `## Answer` 下追加答案，把 `Status:` 改为 `resolved`，然后在 `map.md` 的 Decisions-so-far 中追加上下文摘要和链接。
