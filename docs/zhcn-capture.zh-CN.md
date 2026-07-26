# 原始 zhCN TTS 采集

**简体中文** | [English](zhcn-capture.md)

`src.tools.tts_capture` 记录 `saapi64.dll` 发送到 D4LF Windows 命名管道的 UTF-8 消息。它用于在
解析器或本地化工作之前收集未翻译的 zhCN 样本。

桌面 App 通过一个可选的“诊断采集”（`Diagnostics`）选项卡提供相同格式。需要时，在
“设置 > 高级设置”（`Settings > Advanced`）下启用“显示诊断采集标签页”（`Show Diagnostic Capture Tab`）。
该设置默认禁用。App 采集是首选的收集路径；命令行录制工具仍作为备选。

## 安全与范围

**This recorder never launches or controls Diablo IV. It performs no mouse or keyboard actions.** It
only waits on `\\.\pipe\d4lf` and stores messages that the game has already chosen to send through
`saapi64.dll`.

**本录制工具绝不会启动或控制《暗黑破坏神 IV》，也不会执行任何鼠标或键盘操作。**

录制工具不导入物品解析器，不推断英文物品边界，不移动指针，不按键，不截图，也不更改游戏设置。
它采集所有管道消息，而不仅仅是物品文本。

## 录制之前

- 使用 Windows 和仓库的常规 Python 环境。
- 按照项目 README 中描述的现有 TTS 设置，安装并签名 `saapi64.dll`。
- 将游戏本身配置为 `zhCN` 语言及其辅助功能 TTS 输出。
- 对于 App 采集，关闭任何其他 TTS 监听器，在“设置 > 高级设置”（`Settings > Advanced`）下启用
  “显示诊断采集标签页”（`Show Diagnostic Capture Tab`），并使用 D4LF 的“诊断采集”（`Diagnostics`）选项卡。
- 对于 CLI 采集，关闭 D4LF 和所有其他 TTS 监听器。同一时间只能有一个进程占用 `\\.\pipe\d4lf`。
- 记录确切的游戏 build。两条采集路径都需要它，以免采集与其来源 build 脱节。

## 在 App 中采集

在“设置 > 高级设置”（`Settings > Advanced`）下启用“显示诊断采集标签页”（`Show Diagnostic Capture Tab`），
打开“诊断采集”（`Diagnostics`），选择语言、游戏 build、类别和游戏区域，然后选择
“开始采集”（`Start Capture`）。App 会在正常解析之前截取原始 TTS 负载，并在选择
“结束并保存”（`Stop and Save`）之前阻止新的游戏输入操作。它将带时间戳的 JSONL 和回放文件保存在
`%USERPROFILE%\.d4lf\captures` 下，且绝不上传。

录制工具应在收集样本之前处于活动状态。请自行启动和操作游戏；两条采集路径都不会替你启动或控制它。

## 运行录制工具

在仓库根目录的 PowerShell 中：

```powershell
uv run python -m src.tools.tts_capture `
  --output .\captures\zhCN-3.1.0.72810.jsonl `
  --locale zhCN `
  --game-build 3.1.0.72810 `
  --session-meta area=inventory `
  --session-meta character=rogue
```

`--session-meta KEY=VALUE` 是可选且可重复的。用它记录语言和 build 尚未涵盖的采集上下文。不要在
元数据中放入个人或秘密信息。

继续正常使用游戏。DLL 发出的每条消息都会被记录，无需录制工具执行悬停、点击、按键或其他操作。
在录制工具终端按 `Ctrl+C` 即可干净地停止。

## 输出格式

输出为 UTF-8 JSON Lines。每行是一条完整的 DLL 消息：

```json
{"schema_version":1,"locale":"zhCN","game_build":"2.4.1.12345","session":{"id":"00000000-0000-4000-8000-000000000000","started_at":"2000-01-01T00:00:00.000Z","pipe_name":"\\\\.\\pipe\\d4lf","metadata":{"area":"inventory","character":"rogue"}},"sequence":1,"timestamp":"2000-01-01T00:00:01.000Z","raw_text":"先祖传奇双手剑"}
```

- `schema_version` 当前为 `1`。
- `locale` 和 `game_build` 复制自必需的 CLI 参数。
- `session.id` 是每次运行生成的新 UUID；`session.started_at` 和记录的 `timestamp` 值为 UTC。
- `session.metadata` 包含可选的 `--session-meta` 值。
- `sequence` 从 `1` 开始，每收到一条管道消息递增一次。
- `raw_text` 精确保留解码后的 UTF-8 文本，唯一的例外是 `saapi64.dll` 作为传输终止符添加的单个
  尾部 NUL 字节。

不存在修剪、实体替换、物品分组或英文边界检测。如果 DLL 发送 `CONNECTED`、`DISCONNECTED` 和
`Mouse Button 4` 之类的消息，它们就是普通记录。

## 原子化关闭

记录会写入输出目录中的临时文件。干净停止时，录制工具会刷新并同步该文件，然后原子地替换请求的
输出路径。在此之前，已有的输出文件保持不变。如果采集失败，临时文件会被删除，先前的输出保持原样。

始终使用 `Ctrl+C` 并等待 `Saved ... messages` 确认。关闭终端或终止进程无法保证最后的原子重命名。

## 离线回放

App 会在“结束并保存”（`Stop and Save`）之后自动执行此步骤。对于 CLI 采集，在游戏关闭后，无需连接命名管道或
读取用户配置即可重建物品边界：

```powershell
uv run python -m src.tools.tts_replay `
  --input .\captures\zhCN-3.1.0.72810.jsonl `
  --assets-dir .\assets\lang\zhCN `
  --output .\captures\zhCN-3.1.0.72810-report.json
```

回放命令会校验 UTF-8 JSONL、schema 版本、语言、游戏 build 以及单调递增且唯一的序列号。其报告对
精确的采集内容和语言资产计算哈希，包含每条重建的原始帧，且不含当前时间戳，因此相同输入会产生
完全相同的字节。
