# ![D4LF](assets/logo.png)

**简体中文** | [English](README.en.md)

D4LF 是一个 Windows 上的《暗黑破坏神 IV》装备筛选辅助工具。这个分支基于上游
`v9.3.7`，增加了简体中文界面、中文客户端解析、跨语言 Build 导入、中文巅峰浮层和本地诊断能力。

> [!WARNING]
> 当前版本为 `9.3.7+zhcn.beta.5` 测试版。它并非暴雪授权或背书的软件，也无法保证不会触发
> 游戏规则或反作弊相关风险。请先阅读[账号与自动化风险](#%E8%B4%A6%E5%8F%B7%E4%B8%8E%E8%87%AA%E5%8A%A8%E5%8C%96%E9%A3%8E%E9%99%A9)。

![D4LF 示例](assets/thumbnail.jpg)

## 主要功能

- 在背包和储物箱中按物品类型、强力词缀、词缀数值、稀有度及独有威能筛选装备
- 支持 `English (enUS)` 与 `简体中文 (zhCN)` 客户端和应用界面
- 从 Maxroll、Mobalytics、D4Builds、InfinityBuilds 和暗黑核导入 Build
- 导入装备规则和巅峰路线，并使用稳定内部 ID 实现中英文客户端互通
- 提供高亮/快速视觉模式、巅峰浮层、信息面板和受保护的物品交互
- 可选的本地自动失败留样与手动 TTS 诊断采集，两者均默认关闭

<a id="setup"></a>

## 下载与安装

1. 从[本仓库 Releases](../../releases)下载最新的 Windows `.zip`，解压到普通文件夹。
1. 找到 Diablo IV 安装目录：
   - Battle.net：游戏页齿轮图标 > **在资源管理器中显示**
   - Steam：游戏属性 > **已安装文件** > **浏览**
1. 在解压后的 D4LF 目录中运行 `install_dll.cmd`。
1. 按提示提供 Diablo IV 路径，并允许管理员权限和本地证书安装。
1. 运行 `d4lf.exe`，完成下面的语言、游戏和 Profile 设置。

上游 [d4lfteam/d4lf Releases](https://github.com/d4lfteam/d4lf/releases) 是原版发布渠道，不包含本分支的
完整中文支持。详细操作和故障排查见[完整中文使用手册](docs/full-guide.zh-CN.md)。

## 必须的游戏设置

在 Diablo IV 中确认：

- **高级说明信息**：开启
- **字体大小**：小或中
- **HDR**：关闭
- **使用屏幕阅读器**：开启
- **第三方屏幕阅读器**：开启

在 D4LF 的 **设置 > 系统与路径 > 界面与游戏语言** 中选择与游戏客户端相同的语言：

- 中文游戏：`简体中文 (zhCN)`
- 英文游戏：`English (enUS)`

这个选项会同时切换 D4LF 界面和物品解析资源，但不会修改 Diablo IV 自身的语言。修改后请重启
D4LF。默认按 `F11` 启动装备筛选。

## 导入 Build

在 D4LF 的 **Profile 导入器**中粘贴受支持的 Build 链接。目前支持：

- [Maxroll](https://maxroll.gg/d4/)
- [Mobalytics](https://mobalytics.gg/diablo-4/builds)
- [D4Builds](https://d4builds.gg/builds)
- [InfinityBuilds](https://infinitybuilds.gg/en/builds)
- [暗黑核 D2Core](https://www.d2core.com/d4/builds)

导入器会把来源网站的名称映射为 D4LF 的稳定内部 ID。因此：

- 英文 InfinityBuilds 等来源导入后，可以切换到 `zhCN` 并用于中文游戏
- 中文暗黑核 Build 导入后，可以切换到 `enUS` 并用于英文游戏
- 网站显示语言不决定 Profile 的运行语言；来源站的机器翻译也不作为中文目录的权威依据

导入完成后，请在 **设置 > Profile** 中启用生成的 Profile。新赛季或游戏热修复可能改变物品、
词条和巅峰数据，发布前仍需通过版本清单和实机样本复核。

## 诊断与隐私

**自动保存识别失败样本**默认关闭。启用后，D4LF 只在解析失败时把截图、物品局部图和对应 TTS
保存到本机 `C:/Users/<WINDOWS_USER>/.d4lf/captures/automatic`，不会自动上传。

手动诊断页也默认隐藏且关闭。需要时可在 **设置 > 高级设置** 中开启 **显示诊断采集标签页**，
再使用“开始采集”和“停止并保存”。手动诊断与自动失败留样可以同时开启，但手动采集期间会阻止
新的游戏输入操作。采集说明见[中文采集指南](docs/zhcn-capture.md)。

提交 Issue 前请检查样本内容；不要上传账号名、聊天、好友列表或其他个人信息。仓库的发布前隐私
检查流程见[公开发布说明](docs/public-release.md)。

## 账号与自动化风险

D4LF 会读取屏幕和无障碍 TTS；启用自动整理、标记或移动物品时，还会产生鼠标或键盘输入。
这类工具可能受到 Blizzard EULA、使用条款或反作弊策略约束。目前没有可靠证据能够给出“封号概率”，
前台窗口检查、诊断期间禁用输入等保护也不能消除风险。

请自行判断是否启用交互功能。只使用视觉模式通常减少自动输入，但不代表获得官方许可或零风险。
完整评估见[账号风险说明](docs/zhcn-support-plan.md#account-risk)。

## 数据来源与致谢

简体中文目录优先使用可稳定配对的游戏记录和官方客户端文本：

- [Diablo4Companion](https://github.com/josdemmers/Diablo4Companion)：主要 `enUS`/`zhCN` 稳定 ID 配对
- [DiabloTools/d4data](https://github.com/DiabloTools/d4data)：游戏版本和内部标识校验
- [D2Core](https://www.d2core.com/)：经许可使用的补充数据和交叉校验来源

D2Core 不是唯一权威来源；它缺少某项数据时，不会禁用已有的中文别名。完整许可、归属和版本来源见
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)、[第三方数据说明](docs/third-party-data.md)和
[中文数据更新流程](docs/locale-data-update.md)。上述项目与网站不为本分支背书。

## 开发与验证

项目使用 Python 3.14 和 `uv`：

```powershell
uv sync --frozen --all-groups
uvx prek run --all-files
uv run pytest -p no:cacheprovider -p no:pytest_randomly
```

季节数据候选检查、公开仓库扫描和 Windows 构建均由 GitHub Actions 执行。中文覆盖范围和待实机验证
项目见[中文支持审计](docs/zhcn-scope-audit.md)。

## 项目关系与支持

本分支基于 [d4lfteam/d4lf](https://github.com/d4lfteam/d4lf) `v9.3.7` 开发。中文版本的问题请提交到
本仓库 Issues。README 中的上游 Discord 和 Ko-fi 链接（见完整手册）属于原项目维护者，并非本分支
作者的联系方式或收款渠道。

项目按 [MIT License](LICENSE.txt) 发布。
