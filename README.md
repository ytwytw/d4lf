# D4LF 简体中文增强版

[English](README.en.md)

D4LF 是一个 Windows 桌面装备过滤辅助工具。它通过屏幕画面和《暗黑破坏神 IV》的
无障碍 TTS 文本识别物品，并按照本地 Profile 显示保留或丢弃结果。本分支在上游
[D4LF](https://github.com/d4lfteam/d4lf) V10 基础上增加简体中文客户端解析、双语界面和
跨语言 Build 导入。

> 本项目不是暴雪官方工具。使用任何第三方辅助工具都无法保证账号零风险，请自行判断并承担风险。

![D4LF 界面预览](assets/thumbnail.jpg)

## 主要功能

- 支持简体中文与英文游戏客户端；设置中的语言会同时切换界面和游戏文本解析。
- 按装备类型、物品强度、稀有度、词缀、暗金特效和数值阈值过滤装备。
- 支持物品栏、储物箱、快速视觉模式、匹配高亮、信息面板和巅峰盘悬浮层。
- 从 [Maxroll](https://maxroll.gg/d4/)、[Mobalytics](https://mobalytics.gg/diablo-4/builds)、
  [D4Builds](https://d4builds.gg/)、[InfinityBuilds](https://infinitybuilds.gg/) 和
  [暗黑核 D2Core](https://www.d2core.com/d4/planner) 导入 Build。
- Build 来源语言与游戏语言相互独立：英文 Build 可用于中文或英文客户端，中文 D2Core
  Build 也可用于中文或英文客户端。

## 安装

1. 从本仓库的 [Releases](https://github.com/ytwytw/d4lf/releases) 下载最新 ZIP 并解压。
1. 找到《暗黑破坏神 IV》安装目录。
1. 双击 `install_dll.cmd`，按提示提供游戏目录并允许安装本地签名证书。
1. 启动 `d4lf.exe`，在 `设置 > 系统 > 语言` 中选择游戏客户端实际使用的语言。
1. 在游戏中启用高级说明信息、屏幕阅读器和第三方屏幕阅读器；字体大小使用小或中，关闭 HDR。
1. 导入 Build 或创建 Profile，在设置中启用需要使用的 Profile。
1. 启动游戏后使用主界面显示的热键；默认 `F11` 运行装备过滤。

如果 TTS 一直无法连接，可尝试以管理员身份运行游戏和启动器。配置损坏时，退出 D4LF 后删除
`%USERPROFILE%\.d4lf\params.ini`，再通过设置界面重新配置。

## 跨语言 Build 导入

导入器先把网站数据解析成稳定的内部标识，再根据当前界面和游戏语言显示名称。因此：

| Build 来源                                         | 中文客户端 | 英文客户端 |
| -------------------------------------------------- | ---------- | ---------- |
| 英文 Maxroll、Mobalytics、D4Builds、InfinityBuilds | 支持       | 支持       |
| 中文 D2Core                                        | 支持       | 支持       |

网站内容变化、赛季更新或无法精确匹配的词条会被跳过并记录日志，不会用模糊翻译强行猜测。
导入后请在 Profile 编辑器中检查结果。

## 数据与致谢

中文数据采用多来源聚合和稳定内部标识，不把任一第三方网站视为唯一权威来源。D2Core 数据已获许可，
在本项目中作为补充数据和 Build 来源使用；感谢
[暗黑核 D2Core](https://www.d2core.com/d4/planner) 提供参考与支持。游戏版本或赛季更新后，
仍需结合实际客户端文本和其他可靠来源复核变化。

## 诊断与隐私

- 自动失败留样默认关闭。
- 独立诊断页默认隐藏，需在高级设置中明确启用。
- 留样和诊断数据只保存在本机的 `%USERPROFILE%\.d4lf\captures`。
- 功能不会上传数据，也不会录制麦克风。
- 自动留样仅在识别失败时保存必要的屏幕截图、TTS 文本和清单；手动诊断录制可独立启停。

截图可能包含游戏角色名、聊天或其他屏幕内容。公开报告问题前请先检查并脱敏。

## 开发

项目使用 Python 3.14、[uv](https://docs.astral.sh/uv/) 和 PyQt6，运行环境为 Windows。

```powershell
uv sync
uv run pytest . -m "not selenium" -n logical
uv run prek run -a
```

项目许可证见 [LICENSE](LICENSE)。问题与改进建议请使用
[GitHub Issues](https://github.com/ytwytw/d4lf/issues)。
