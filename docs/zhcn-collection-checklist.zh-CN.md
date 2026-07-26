# zhCN 客户端收集清单

**简体中文** | [English](zhcn-collection-checklist.md)

这是来自真实 `zhCN` 客户端的第一轮最低限度证据。已提交的语法当前引用 build `3.1.0.72810`；不要
给其他 build 制作的采集重新贴标签。

第一轮仅限装备。不要求非装备背包物品，D4LF 的可选符印（sigil）和贡品（tribute）过滤器与装备
里程碑保持分离。

## 安全规则

- 在“设置 > 高级设置”（`Settings > Advanced`）下启用“显示诊断采集标签页”（`Show Diagnostic Capture Tab`），
  然后使用 D4LF 的“诊断采集”（`Diagnostics`）选项卡进行常规收集。该设置默认禁用，且该选项卡从
  D4LF 已占用的管道录制。
- 不要在 D4LF 打开时运行独立录制工具。只有一个进程能占用 `\\.\pipe\d4lf`。
- 不要使用自动化、宏、脚本化悬停、内存检查或游戏数据转储工具。
- 不要录制 BattleTag、聊天、好友列表、账号电子邮件或其他个人信息。
- 每个 App 会话都以“结束并保存”（`Stop and Save`）结束，并等待已保存状态。

## App 工作流

1. 打开 D4LF，在“设置 > 高级设置”（`Settings > Advanced`）下启用“显示诊断采集标签页”
   （`Show Diagnostic Capture Tab`），并选择“诊断采集”（`Diagnostics`）选项卡。
1. 选择“简体中文 (zhCN)”（`Simplified Chinese (zhCN)`），输入或检测确切的四段式游戏 build，并选择类别和区域。
1. 选择“开始采集”（`Start Capture`）。采集进行期间会阻止新的游戏输入操作。
1. 操作《暗黑破坏神 IV》，手动悬停每个样本。
1. 选择“结束并保存”（`Stop and Save`）。D4LF 保存原始 JSONL 并自动创建离线回放报告。
1. 使用“打开文件夹”（`Open Folder`）打开 `%USERPROFILE%\.d4lf\captures`。

D4LF 生成唯一的带时间戳文件名，绝不覆盖较早的采集。在采集进行中关闭 App 也会完成采集收尾。
回放失败不会删除原始 JSONL。

## CLI 备选

独立录制工具仍可用于恢复和开发。先关闭正常的 D4LF，然后为下面每个部分使用单独的 JSONL 文件。
只更改文件和 `category` 值：

```powershell
uv run python -m src.tools.tts_capture `
  --output .\captures\zhCN-3.1.0.72810-core.jsonl `
  --locale zhCN `
  --game-build 3.1.0.72810 `
  --session-meta area=inventory `
  --session-meta category=core
```

无论哪种工作流，都要手动悬停每个物品，等待屏幕阅读器读完，手动移开，然后继续。录制中包含菜单
和其他噪音没有关系；离线回放工具会保留并界定它们。

## 会话 1：框架核心

目标：约 12 到 18 件普通物品。

- 在可获得时，各一件普通、魔法、稀有、传奇、暗金和神话物品。
- 至少一件武器、一件护甲和一件首饰。
- 一件先祖物品和一件非先祖物品。
- 一件已装备物品和一件背包物品。
- 一件商人物品（如果已经方便查看）。
- 一件带空插槽的物品、一件带刻印威能的物品和一件带需求等级行的物品。

此会话确认确切的中文稀有度/类型标题、物品强度锚点、词缀标题、停止标记以及鼠标/动作按钮终止符。
它是最高优先级的采集。

## 会话 2：护符装备（可选资料片范围）

仅当 Lord of Hatred 的护符装备过滤属于期望范围时，使用 `category=talisman`：

- 来自不同套装的两个护身符。
- 来自不同稀有度或套装的两个印记，包括所有口述词缀行。
- 一个暗金护身符或神话印记（如果已经拥有）。

这些是 D4LF 和当前游戏内置拾取过滤器都支持的类装备过滤目标。不要仅为此任务刷取或购买缺失的样本。

## 会话 3：D4LF 扩展过滤器（可选非装备范围）

仅当需要 D4LF 装备以外的过滤器时，使用 `category=extended-filters`：

- 两个具有不同地下城和词缀组合的梦魇符印。
- 一个 escalation/bloodied 符印（如果可获得）。
- 两个不同稀有度的贡品。

公开的配对数据已经映射了 Nightmare Sigil 物品类型。这些采集仅用于特殊 TTS 布局、地下城和词缀
解析。纯装备支持不需要它们。

## 不要收集

不要在这些历史解析器类型上花费客户端时间：

- `Elixir` 和 `Incense`：随 Lord of Hatred 已从当前赛季领域移除。
- `Material` 和 `TemperManual`：非装备，在 D4LF 配置文件过滤之前就被忽略。
- `Tome`：d4data 将其识别为不可装备的 `SkillPointTome`，不是武器或副手。

## 推迟的定向采集

暂时不要追查未解决的威能或暗金列表。必须先核对公开当前赛季来源和稳定 ID。之后的请求只应在核对
完成后其中文 TTS 文本或布局仍然含糊时，点名一个确切可获取的物品。

## 视觉证据

原始命名管道 JSONL 比音频或通用屏幕录制更有用。

- 仅当回放选择了错误的开始/结束行、词缀高亮位置不对，或已装备/商店布局与背包不同时，才截取
  全屏 PNG。
- 如果仅凭 JSONL 加截图无法理解顺序，制作一个展示单次手动悬停的短视频。避免录制无关 UI。
- 当 UTF-8 TTS 文本已成功采集时，不需要音频录制。

## 回放与交接

选择“结束并保存”（`Stop and Save`）时，App 会自动创建回放报告。对于 CLI 采集，仅在关闭游戏后回放每个会话：

```powershell
uv run python -m src.tools.tts_replay `
  --input .\captures\zhCN-3.1.0.72810-core.jsonl `
  --assets-dir .\assets\lang\zhCN `
  --output .\captures\zhCN-3.1.0.72810-core-report.json
```

App 采集保留在 `%USERPROFILE%\.d4lf\captures` 下。CLI 采集和任何匹配的 PNG/视频可以保留在仓库
被忽略的 `captures/` 目录下。原始 JSONL 是事实来源。解析器更改后始终可以重新生成回放报告。
