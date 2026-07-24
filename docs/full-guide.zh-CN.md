# ![logo](../assets/logo.png)

**简体中文** | [English](full-guide.en.md)

根据词缀、威能及其数值阈值，筛选背包和储物箱中的装备与梦魇地下城钥匙。如有问题、功能建议或
错误报告，请在本仓库提交 GitHub Issue。

![示例](../assets/thumbnail.jpg)

## 功能

- 筛选背包和储物箱中的物品
- 按物品类型、物品强度和强力词缀数量筛选
- 按词缀及其数值筛选，并可为单个词缀指定强力词缀要求
- 按物品稀有度筛选词缀和梦魇地下城钥匙，例如只保留稀有制作底材，不保留同词缀的传奇物品
- 按暗金物品的词缀和独有威能数值筛选
- 按词缀、稀有度、护符套装或独有威能筛选圣化徽记和护符
- 通过地下城和词缀的黑名单、白名单筛选梦魇地下城钥匙
- 按名称或稀有度筛选贡品
- 快速移动储物箱或背包中的物品
- 支持 16:10 到 21:9 之间的所有宽高比
- 信息面板浮层，可跟踪世界事件和本次游戏统计
- 巅峰浮层，可从受支持的 Build 规划网站导入（Mobalytics、Maxroll、D4Builds）
- 本地采集原始无障碍 TTS，并自动离线回放诊断

## 数据来源与致谢

简体中文目录优先采用按稳定 ID 配对的游戏数据和官方客户端文本。
[Diablo4Companion](https://github.com/josdemmers/Diablo4Companion) 提供了主要的 `enUS`/`zhCN` 稳定 ID
配对数据，[DiabloTools/d4data](https://github.com/DiabloTools/d4data) 用于校验游戏版本和内部标识；两者
均按 MIT License 使用，完整声明见 [`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md)。
[D2Core 公开的《暗黑破坏神 IV》数据库](https://www.d2core.com/)仅用于补充和交叉校验，不作为
权威数据源（source of truth）；D2Core 快照中缺失某项时，绝不会因此禁用已有的中文别名。每次发布生成的清单会保留
所用来源的游戏版本标识、URL、哈希值和逐条数据来源。D2Core 不为本项目背书。

<a id="setup"></a>

## 安装与设置

### 安装和快速入门（第 12 赛季必须遵循的新说明）

- 本简体中文分支请从[本仓库 Releases](../../releases)下载并解压最新版本（`.zip`）。上游
  [d4lfteam/d4lf Releases](https://github.com/d4lfteam/d4lf/releases) 是历史英文发行渠道。
- 找到你的“Diablo IV”安装目录，并复制路径：
  - Battle.net：点击“开始游戏”按钮旁的齿轮图标，然后选择“在资源管理器中显示”
  - Steam：右键点击游戏，选择“管理 > 浏览本地文件”
- D4LF 通过读取屏幕以及游戏为无障碍功能发送的 TTS 信息获取物品信息。TTS 需要额外设置，详见
  [TTS 章节](#tts)。关于 `install_dll.cmd` 脚本：
  - 进入下载并解压后的 D4LF 目录
  - 双击 `install_dll.cmd`
    - 如果系统请求管理员权限，请允许
    - 出现提示时，输入 Diablo IV 的安装路径
    - 出现证书安装提示时，请允许
    - 如果全部成功，请继续本指南；否则请在本仓库提交 GitHub Issue
- 创建用于定义《暗黑破坏神 IV》物品筛选规则的 Profile，可选择：
  - 运行 `d4lf.exe`，在导入窗口中粘贴主流 Build 规划网站的页面链接
  - 参考下方[筛选规则与 Profile](#how-to-filter--profiles)，再通过 Profile 编辑器自行创建
- 如果手动创建 Profile（不推荐），请放入 `C:/Users/<WINDOWS_USER>/.d4lf/profiles`。D4LF 设置窗口
  提供直接打开该文件夹的按钮；导入的 Profile 会自动保存到这里。
- 运行 `d4lf.exe`，在设置的 Profile 区域启用需要使用的 Profile。
- 确认所有[游戏设置](#game-settings)均正确。
- 如果修改了设置，请重启 `d4lf.exe`，然后启动 Diablo IV。
- 使用 `d4lf.exe` 中列出的快捷键执行筛选。默认按 **F11** 运行装备筛选器。
- 常见问题通常会在 `d4lf.exe` 启动时显示错误或警告。如需更多帮助，请在本仓库提交 GitHub Issue。

<a id="game-settings"></a>

### 游戏设置

- 在 D4LF 中，将**设置 > 系统与路径 > 界面与游戏语言**设为与 Diablo IV 客户端相同的语言。
  这一项会同时切换 D4LF 界面以及物品文本/解析器资源。
- `English (enUS)` 和 `简体中文 (zhCN)` 均支持受保护的装备筛选交互。候选版本会禁用上游自动更新器，
  防止本中文分支被官方英文版本覆盖。诊断采集期间，以及 Diablo IV 不是前台窗口时，所有游戏输入
  都会被阻止。D4LF 的语言设置不会修改已安装 Diablo IV 客户端自身的语言。
- **重要：** 必须在“选项 > 游戏功能 > 游戏功能”中启用“高级说明信息”。否则物品解析会非常不稳定，
  而且程序可能不会提示哪里出了问题。
- “图像”设置中的字体大小必须为“小”或“中”。
- HDR 会使画面过亮，导致 D4LF 无法识别屏幕上某些物品的状态，因此必须关闭。
- 必须在“选项 > 辅助功能”中启用“使用屏幕阅读器”。
- 必须在“选项 > 辅助功能”中启用“第三方屏幕阅读器”。安装 DLL 后语音会消失，参见上面的快速入门。

### 账号与自动化风险

D4LF 并非暴雪授权或背书的工具，也没有可靠依据可以给出账号受处罚的具体概率。自动键盘或鼠标交互
可能受到暴雪 EULA 或反作弊政策约束。受保护交互会在诊断采集期间以及 Diablo IV 不是前台窗口时阻止
输入，但这些保护不能消除账号风险。自动失败截屏默认关闭；诊断采集和截屏仅保存在本机，除非用户主动
分享。完整说明见[账号风险评估](zhcn-support-plan.md#account-risk)。

### 常见问题

- 工具显示“尚未建立 TTS 连接”，但我已经正确完成设置。
  - 这表示 D4LF 已确认 DLL 位于正确位置，但仍未建立 TTS 连接。最常见的原因是 Windows 用户权限
    不允许 Diablo IV 连接第三方屏幕阅读器。请尝试以下步骤：
    - 将 Diablo IV 设置为以管理员身份运行。首先进入 Diablo IV 安装目录。
      - Steam：右键点击游戏并选择“属性”，进入“已安装文件”，点击“浏览”。
      - Battle.net：在游戏页面点击齿轮图标，选择“在资源管理器中显示”。
    - 右键点击 `Diablo IV.exe`，打开“属性”，在“兼容性”页勾选“以管理员身份运行此程序”。
    - 通过 Steam/Battle.net 再次运行 Diablo IV，确认问题是否解决。
    - 如果仍未解决，也将 Steam/Battle.net 设置为以管理员身份运行，并确保从对应平台启动游戏。
- GUI 打开后立即崩溃，而且没有错误信息。
  - 这几乎总是设置后端文件 `params.ini` 存在问题。删除
    `C:/Users/<WINDOWS_USER>/.d4lf/params.ini`，重新打开 GUI，并通过 D4LF 设置窗口完成配置。使用
    GUI 管理设置可保证文件格式正确。
- 无法控制鼠标。
  - 由于本机 Windows 设置，工具可能无法控制鼠标。请尝试以管理员身份运行。如果不希望使用管理员
    权限，可以启用“设置 > 自动化 > 仅视觉模式”，完全禁用鼠标控制。

<a id="tts"></a>

### TTS

D4 使用名为 Tolk 的第三方 TTS 引擎。Tolk 支持加载自定义第三方 TTS DLL。D4 会自动加载该 DLL；
它不会朗读内容，而是将文本发送给另一个应用程序。其工作方式类似于供 D4 使用的盲文 TTS 应用。

Diablo IV 只会加载已签名的 TTS DLL（`saapi64.dll`）。`install_dll.cmd` 会自动完成以下操作：

- 将 DLL 文件复制到 Diablo IV 目录
- 下载用于给 DLL 添加本地签名的 `signtool`
- 运行 `signtool` 并签名 DLL

### TTS 诊断采集

手动诊断采集默认关闭。需要使用时，先在**设置 > 高级设置**中打开**显示诊断采集标签页**。该标签页
可以记录原始无障碍 TTS 数据流，本功能不会启动或控制 Diablo IV。选择语言、准确的游戏版本、类别和
游戏区域，然后点击“开始采集”和“停止并保存”。采集数据与离线回放报告保存在本机
`C:/Users/<WINDOWS_USER>/.d4lf/captures`；D4LF 不会上传这些文件。诊断采集期间会阻止新的游戏输入。
此开关与同样默认关闭的“自动保存识别失败样本”相互独立。

## GUI 概览

`d4lf.exe` 是统一操作入口，可启动 D4LF 进程并完成全部配置。

如果更喜欢独立的纯控制台体验，可运行 `d4lf-consoleonly.bat`，它不会打开 GUI。不过仍建议使用 GUI
管理配置。

当前功能：

- 从暗黑核、Maxroll、D4Builds、Mobalytics、InfinityBuilds 导入 Build
- 通过设置窗口完整管理配置
- 测试版手动 Profile 编辑器/创建器

### 主界面

（文档仍在编写中）

主界面会显示 D4LF 筛选物品时的活动日志，所有错误也会显示在这里。

界面包含前往 Profile 导入器、设置和 Profile 编辑器的导航按钮。

### Profile 导入器

（文档仍在编写中）

可从以下主流 Build 网站导入 Profile：暗黑核、Maxroll、Mobalytics、D4Builds、InfinityBuilds。

导入器中的大部分功能都有界面说明，将鼠标悬停在选项上可查看详细信息。

### 设置窗口

设置窗口用于配置 D4LF 的所有功能。

![设置窗口](../assets/readme/settings.png)

窗口内已为每项设置提供说明，可逐项查看感兴趣的选项。

以下是经常修改的设置区域：

#### 界面与游戏语言

通过**系统与路径 > 界面与游戏语言**在 `English (enUS)` 与 `简体中文 (zhCN)` 之间切换。选定语言会
同时控制应用界面和 Diablo IV 物品文本/解析器语言。请另外将 Diablo IV 设置为相同语言。诊断采集
运行期间会阻止全部游戏输入；采集停止后，两种语言均支持正常的受保护装备筛选交互。

#### Profile

这里用于启用或停用 Profile。拖动六点图标可以调整顺序。使用“带高亮的视觉模式”时，将物品悬停后，
列表最上方的 Profile 会决定显示方框所用的规则，因此顺序可能会影响显示。不过，只要物品匹配任意
Profile，它就会被保留。

#### 战利品行为

这里可以设置如何处理完全不匹配任何筛选规则的物品，例如暗金物品或力量法典升级。

#### 储物箱与转移

请正确设置当前可用的储物箱页数。如果没有购买任何资料片，请将“最大储物箱页数”改为 6。

在解锁全部可用储物箱页之前，D4LF 无法正确处理储物箱。

#### 界面与主题

这里可以切换深色或浅色模式。

本区域还包含两种可以互相切换的视觉模式。

启用 `highlight_matches` 后，匹配词缀的项目符号会在屏幕上显示绿色方框。这是经典视觉模式，但速度
稍慢，也可能因屏幕词缀位置识别而偶尔出错。

![设置 - 高亮匹配项](../assets/readme/settings-highlight_matches.jpg)

如果改用 `fast` 视觉模式，程序不会读取屏幕，而是立即在屏幕上显示相关信息。快速视觉模式支持手柄。
两种模式显示相同的信息，只是呈现方式不同。

![设置 - 快速模式](../assets/readme/settings-fast.jpg)

如需更改快速视觉模式方框的位置，请前往“设置 > 高级 > 快速视觉模式坐标”。

### Profile 编辑器

（文档仍在编写中）

Profile 编辑器用于编辑 Profile，目前仍处于测试阶段。“梦魇地下城钥匙”标签页支持全局词缀规则
（无需选择地下城即可在所有钥匙上拉黑某个词缀）和钥匙稀有度门槛；“词缀”标签页也提供词缀稀有度
选择器。

<a id="how-to-filter--profiles"></a>

## 筛选规则与 Profile

所有 Profile 都定义白名单筛选规则。如果所有 Profile 中都没有规则匹配某件物品，该物品会被标记为
丢弃。

程序会在启动时验证配置文件。如果结构或语法错误，程序将停止启动，错误消息会提示具体问题。

以下章节说明 Profile 中可使用的各种筛选器。YAML 文件如何组织由你决定：可以把所有筛选器放在一个
文件中，也可以按类型分别保存，甚至可以将同类筛选器拆分到多个文件。最终，“设置”的 Profile 区域
中启用的所有 Profile 都会参与判断。只要其中一个 Profile 要求保留物品，无论其他 Profile 如何配置，
该物品都会被保留。同样，如果所有 Profile 都缺少某类筛选器，例如都没有 `Sigils`，那么对应类型的
所有物品（本例中为梦魇地下城钥匙）都会被保留。

<a id="affix--unique-aspect-filter-syntax"></a>

### 词缀/独有威能筛选语法

物品的威能或词缀有两种配置方式。无论采用哪种方式，都建议先导入一个 Profile，再以此为基础修改。

- 推荐使用 GUI 中的“编辑 Profile”窗口
- 也可以手动编辑 Profile

下方说明主要面向手动编辑文件，但相关概念同样适用于 GUI。

<details><summary>示例</summary>

```yaml

# 筛选攻击速度
- { name: attack_speed }
# 筛选攻击速度并设置阈值。
# 当说明范围递增时保留较大数值；当范围递减时保留较小数值。
- { name: attack_speed, value: 4 }
# 筛选达到潜在最大值 50% 以上的攻击速度词缀
- { name: attack_speed, minPercentOfAffix: 50 }
```

</details>

<a id="affixes"></a>

### 词缀

词缀筛选由顶层键 `Affixes` 定义，其中包含要应用的筛选规则列表。每条规则都有名称，并可组合使用以下
条件：

- `itemType`：单个物品类型名称或多个类型的列表。
  参见 [assets/lang/enUS/item_types.json](../assets/lang/enUS/item_types.json)
- `rarity`：规则匹配的单个稀有度或稀有度列表。为空或省略时匹配全部稀有度。值不区分大小写。
  详情及可用值参见[按稀有度筛选](#filtering-on-rarity)和
  [rarity.py](../src/item/data/rarity.py)
- `minPower`：最低物品强度
- `minGreaterAffixCount`：整件物品所需的最少强力词缀数量。详情参见
  [强力词缀筛选](#greater-affix-filtering)
- `affixPool`：由多组规则构成的列表。每组规则都必须满足，否则丢弃物品
  - `count`：定义词缀列表（参见[语法](#affix--unique-aspect-filter-syntax)），并可指定
    `minCount`、`maxCount` 和 `minGreaterAffixCount`
    - `minCount`：物品必须匹配的最少词缀数量，默认为列出的词缀数量
    - `maxCount`：物品允许匹配的最多词缀数量，默认为列出的词缀数量
- `inherentPool`：规则与 `affixPool` 相同，但针对物品的固有词缀判断
- `uniqueAspect`：用于查找特定暗金物品，支持以下属性：
  - `name`：（必填）要查找的暗金物品名称，列表见
    [uniques.json](../assets/lang/enUS/uniques.json)
  - `value`：独有威能必须达到的最小数值，不能与 `minPercentOfAspect` 同时使用
  - `minPercentOfAspect`：不指定固定值，而是要求达到潜在最大值的百分比。详情参见
    [按词缀百分比筛选](#filtering-on-percent-of-affix-instead-of-value)

<details><summary>配置示例</summary>

```yaml
Affixes:
  # 查找物品强度至少为 725，且 affixPool 中至少有 3 条词缀的胸甲和裤子
  - NiceArmor:
      itemType: [ chest armor, pants ]
      minPower: 725
      affixPool:
        - count:
            - { name: dexterity, value: 33 }
            - { name: damage_reduction, value: 5 }
            - { name: lucky_hit_chance, value: 3 }
            - { name: total_armor, value: 9 }
            - { name: maximum_life, value: 700 }
          minCount: 3

  # 查找物品强度至少为 900，且 affixPool 中至少有 3 条词缀的胸甲。
  # 物品必须有 2 条强力词缀，但它们不一定属于 affixPool。
  # 有关 GA 筛选的详情参见“强力词缀筛选”
  - NiceArmor:
      itemType: chest armor
      minPower: 900
      affixPool:
        - count:
            - { name: dexterity }
            - { name: damage_reduction }
            - { name: lucky_hit_chance }
            - { name: total_armor }
            - { name: maximum_life }
          minCount: 3
          minGreaterAffixCount: 2

  # 查找至少有 2 条指定词缀，且固有词缀为最大闪避次数或缩短闪避冷却时间的靴子
  - GreatBoots:
      itemType: boots
      minPower: 800
      inherentPool:
        - count:
            - { name: maximum_evade_charges }
            - { name: attacks_reduce_evades_cooldown_by_seconds }
          minCount: 1
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }
            - { name: cold_resistance }
            - { name: lightning_resistance }
          minCount: 2

  # 查找至少有 2 条指定词缀，并且必须是悔罪护胫的靴子
  # 该暗金物品对被冻伤敌人的伤害乘数至少为 19%（取值范围 15-25）
  # 普通靴子即使有移动速度和冰霜抗性也不会匹配，只有悔罪护胫会匹配
  - GreatUniqueBoots:
      itemType: boots
      minPower: 800
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }
            - { name: cold_resistance }
            - { name: lightning_resistance }
          minCount: 2
      uniqueAspect:
        - name: penitent_greaves
          minPercentOfAspect: 50

  # 也可以同时查找多个独有威能，例如无论 Build 如何都保留数件毕业暗金
  # 保留所有物品强度为 900 的悔罪护胫或戈尔的毁灭之握
  - HighPowerUniques:
      minPower: 900
      uniqueAspect:
        - name: penitent_greaves
        - name: gohrs_devastating_grips

  # 查找带移动速度，并且在全部抗性池中带有 1 条抗性的靴子。
  # 因为一件物品不可能有多条同类抗性词缀，所以抗性组无需设置 maxCount
  - ResBoots:
      itemType: boots
      minPower: 800
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }
        - count:
            - { name: shadow_resistance }
            - { name: cold_resistance }
            - { name: lightning_resistance }
            - { name: fire_resistance }
            - { name: poison_resistance }
          minCount: 1

  # 查找带移动速度的靴子。整件物品至少有两条强力词缀，但不要求具体是哪两条
  - GreaterAffixBoots:
      itemType: boots
      minPower: 800
      minGreaterAffixCount: 2
      affixPool:
        - count:
            - { name: movement_speed, value: 16 }

  # 保留所有先祖物品，即使它们不匹配其他筛选规则
  - AncestralMatch:
      minPower: 900
```

</details>

词缀名称使用小写字母，并以下划线代替空格。完整名称列表见
[assets/lang/enUS/affixes.json](../assets/lang/enUS/affixes.json)。

<a id="filtering-on-rarity"></a>

### 按稀有度筛选

使用 `rarity` 将词缀规则限制为特定物品稀有度。

- 省略 `rarity` 时，规则匹配全部稀有度。
- `rarity` 可接受单个值（`rarity: rare`）或列表（`rarity: [common, magic, rare]`）。

有效稀有度见 [rarity.py](../src/item/data/rarity.py)。

<details><summary>配置示例</summary>

```yaml
Affixes:
  # 只保留带有这些词缀的稀有胸甲。相同词缀的传奇胸甲不会被本规则保留。
  - RareCraftBase:
      itemType: chest armor
      rarity: rare
      affixPool:
        - count:
            - { name: dexterity }
            - { name: maximum_life }
            - { name: total_armor }
          minCount: 2

  # 保留普通、魔法或稀有靴子作为制作底材
  - CraftBoots:
      itemType: boots
      rarity: [common, magic, rare]
      affixPool:
        - count:
            - { name: movement_speed }
          minCount: 1
```

</details>

<a id="filtering-on-percent-of-affix-instead-of-value"></a>

### 按词缀百分比而不是固定数值筛选

除了固定数值，还可以按词缀最低百分比筛选。例如某件物品的力量取值范围为 100-150，如果将力量的
`minPercentOfAffix` 设为 50（即 50%），则保留 125 及以上的数值，丢弃低于 125 的数值。

强力词缀始终视为满足 `minPercentOfAffix`。无需为 `value` 或 `minPercentOfAffix` 指定数值越大越好
还是越小越好，程序会根据词缀范围自动判断。

同一词缀不能同时设置 `minPercentOfAffix` 和 `value`，二者只能选一个。

这些规则也适用于 `uniqueAspect` 和 `GlobalUniques` 中的 `minPercentOfAspect`。

<details><summary>配置示例</summary>

```yaml
Affixes:
  # 查找物品强度至少为 925，且 affixPool 中至少有 3 条词缀的胸甲。
  # damage_reduction 必须大于 40，护甲必须达到其潜在最大词缀值的 70%
  - NiceArmor:
      itemType: chest armor
      minPower: 925
      affixPool:
        - count:
            - { name: dexterity }
            - { name: damage_reduction, value: 40 }
            - { name: lucky_hit_chance }
            - { name: armor, minPercentOfAffix: 70 }
            - { name: maximum_life }
          minCount: 3

```

</details>

<a id="greater-affix-filtering"></a>

### 强力词缀筛选

D4LF 提供两种互补方式，按强力词缀筛选物品：

#### 1. 物品级强力词缀数量（`minGreaterAffixCount`）

无论具体是哪些词缀，此条件都要求整件物品至少具有指定数量的强力词缀。

<details><summary>示例</summary>

```yaml
Affixes:
  - GreaterAffixBoots:
      itemType: boots
      minGreaterAffixCount: 2  # 整件物品至少有 2 条强力词缀
      affixPool:
        - count:
            - { name: movement_speed }
            - { name: maximum_life }
            - { name: strength }
            - { name: fire_resistance }
          minCount: 3
```

</details>

#### 2. 单个词缀的强力要求（`want_greater`）

使用 Profile 编辑器 GUI 或通过导入器导入词缀时，可以为特定词缀勾选“强力”。Profile 中对应
`want_greater`，表示优先要求成为强力词缀的词缀列表。物品级 `minGreaterAffixCount` 仍然生效。
例如两个词缀标记了 `want_greater`，但 `minGreaterAffixCount` 为 1，只要其中任意一个是强力词缀，
物品就会被保留。如果这两个词缀都不是强力词缀，即使其他词缀是强力词缀，该物品也不会被保留。

<details><summary>示例</summary>

```yaml
Affixes:
  - PerfectBoots:
      itemType: boots
      affixPool:
        - count:
            - { name: movement_speed, want_greater: true }  # 必须是强力词缀
            - { name: maximum_life, want_greater: true }    # 必须是强力词缀
            - { name: strength }                            # 可以是普通或强力词缀
            - { name: fire_resistance }                     # 可以是普通或强力词缀
          minCount: 3
      minGreaterAffixCount: 2  # GUI 启用“自动同步”或导入器勾选“要求强力词缀”时自动设置
```

**会匹配：** 带有 movement_speed（强力）、maximum_life（强力）、cold_resistance（普通）和
fire_resistance（普通）的靴子。\
**原因：** movement_speed 和 maximum_life 都按要求成为强力词缀，而且物品有 4 条词缀，满足
`minCount: 3`。

**不会匹配：** 带有 movement_speed（普通）、maximum_life（强力）、cold_resistance（普通）和
fire_resistance（普通）的靴子。\
**原因：** movement_speed 标记为 `want_greater: true`，但物品上的该词缀不是强力词缀。

</details>

#### 常见用法

<details><summary>示例</summary>

**“我想要至少有 2 条强力词缀的靴子，不在乎具体是哪两条”**

```yaml
- itemType: boots
  minGreaterAffixCount: 2
  affixPool:
    - count:
        - { name: movement_speed }
        - { name: maximum_life }
        - { name: strength }
        - { name: fire_resistance }
      minCount: 3
```

**“我想要 movement_speed 必须是强力词缀的靴子”**

```yaml
- itemType: boots
  minGreaterAffixCount: 1  # 此值很重要；如果为 0，movement_speed 就不必是强力词缀
  affixPool:
    - count:
        - { name: movement_speed, want_greater: true }
        - { name: maximum_life }
        - { name: strength }
        - { name: fire_resistance }
      minCount: 3
```

**“我想要 movement_speed 和 maximum_life 都必须是强力词缀的靴子”**

```yaml
- itemType: boots
  minGreaterAffixCount: 2  # 设为 2，要求两者都是强力词缀
  affixPool:
    - count:
        - { name: movement_speed, want_greater: true }
        - { name: maximum_life, want_greater: true }
        - { name: strength }
        - { name: fire_resistance }
      minCount: 3
```

**“我想要 movement_speed 或 maximum_life 中任意一个是强力词缀的靴子”**

```yaml
- itemType: boots
  minGreaterAffixCount: 1  # 设为 1，要求两者之一是强力词缀
  affixPool:
    - count:
        - { name: movement_speed, want_greater: true }
        - { name: maximum_life, want_greater: true }
        - { name: strength } # 如果只有 strength 是强力词缀，而前两者都不是，则不会匹配
        - { name: fire_resistance }
      minCount: 3
```

</details>

### 圣化徽记与护符

圣化徽记和护符分别由顶层键 `Seals` 与 `Charms` 定义。如果没有对应筛选器，该类型的全部物品都会被
保留。

两部分均支持：

- `rarity`：规则匹配的单个稀有度或稀有度列表
- `minGreaterAffixCount`：圣化徽记或护符所需的最少强力词缀数量
- `affixPool`：与装备词缀筛选器相同的规则结构，但匹配圣化徽记或护符上的词缀
- `uniqueAspect`：用于独有护符或神话圣化徽记

`Charms` 还支持：

- `set`：一个或多个护符套装名称；护符属于任一所列套装即可匹配

圣化徽记词缀名称见
[assets/lang/enUS/seals_affixes.json](../assets/lang/enUS/seals_affixes.json)，护符词缀名称见
[assets/lang/enUS/charms_affixes.json](../assets/lang/enUS/charms_affixes.json)，护符套装名称见
[assets/lang/enUS/sets.json](../assets/lang/enUS/sets.json)。独有护符和神话圣化徽记与其他暗金筛选器共用
[uniques.json](../assets/lang/enUS/uniques.json) 中的名称。

<details><summary>配置示例</summary>

```yaml
Seals:
  # 保留带 cooldown_reduction、狂战士熔炉专属狂暴持续时间或护符插槽中任一词缀的圣化徽记。
  # 注意，所需套装名称包含在词缀 ID 中。
  - UtilitySeal:
      affixPool:
        - count:
            - { name: cooldown_reduction }
            - { name: berserkers_crucible_berserking_duration }
            - { name: charm_slot }
          minCount: 1

  # 保留这个指定的神话圣化徽记
  - Mythic Seal:
      uniqueAspect:
        - name: seal_of_the_diamond_mind

Charms:
  # 保留“巢穴之母之力”套装中的任意护符
  - DenMotherSet:
      set: [might_of_the_den_mother]

  # 保留带最大生命的亚瑞特的承载
  - ArreatsBearing:
      affixPool:
        - count:
          - { name: maximum_life }
      uniqueAspect:
        - name: arreats_bearing

  # 保留带 maximum_life 的稀有护符
  - RareLifeCharm:
      rarity: rare
      affixPool:
        - count:
            - { name: maximum_life }
```

</details>

神话圣化徽记始终会被保留，即使不匹配任何 Profile。

### `AspectUpgrades`

可以把希望在获得升级时收到通知的传奇威能放入 Profile。它们由顶层键 `AspectUpgrades` 定义。

此筛选器通常用于 Build 需要的威能。当获得更高等级的力量法典升级时，你可以立即前往秘术师更新。
程序会收藏该物品，并在悬停时显示橙色文字或橙色高亮。

如果物品匹配其他任意 Profile，本筛选器不会产生额外操作。它遵循 `mark_as_favorite` 配置。未匹配
本筛选器且不是力量法典升级的其他威能，由 `keep_aspects` 配置处理。

<details><summary>配置示例</summary>

```yaml
AspectUpgrades:
  # 如果雪幕冒险者长裤可以升级力量法典，就将其标记为收藏；否则忽略
  - of_singed_extremities
  - snowveiled
```

```yaml
# 与上面的效果完全相同，只是格式不同
AspectUpgrades: [of_singed_extremities, snowveiled]
```

</details>

威能名称使用小写字母，并以下划线代替空格。完整名称列表见
[assets/lang/enUS/aspects.json](../assets/lang/enUS/aspects.json)。

### 梦魇地下城钥匙

梦魇地下城钥匙由顶层键 `Sigils` 定义，其中包含需要筛选的词缀或地点名称列表。如果没有 `Sigils`
筛选器，则保留所有钥匙。

<details><summary>配置示例</summary>

```yaml
Sigils:
  blacklist:
    # 地点
    - endless_gates
    - vault_of_the_forsaken

    # 词缀
    - armor_breakers
    - resistance_breakers
```

如果希望只保留特定词缀或地点，也可以使用 `whitelist`。即使存在 `whitelist`，`blacklist` 仍会丢弃
匹配任何黑名单词缀或地点的钥匙。

```yaml
# 只保留 vault_of_the_forsaken，并且不能带 armor_breakers 或 resistance_breakers
Sigils:
  blacklist:
    - armor_breakers
    - resistance_breakers
  whitelist:
    - vault_of_the_forsaken
```

如需反转优先级，添加值为 `whitelist` 的 `priority`。

```yaml
# 保留全部 vault_of_the_forsaken，即使带有 armor_breakers 或 resistance_breakers
Sigils:
  blacklist:
    - armor_breakers
    - resistance_breakers
  whitelist:
    - vault_of_the_forsaken
  priority: whitelist
```

也可以根据单个词缀或地点创建条件筛选器。

```yaml
# 只保留同时带有 shadow_damage 的 iron_hold
Sigils:
  blacklist:
    - armor_breakers
    - resistance_breakers
  whitelist:
    - [ iron_hold, shadow_damage ]
```

</details>

可以使用顶层 `rarity` 按稀有度限制钥匙。钥匙稀有度根据
[assets/lang/enUS/sigils.json](../assets/lang/enUS/sigils.json) 中的词缀推导。

- 省略 `rarity` 时，全部钥匙稀有度均可通过。
- 稀有度门槛先于黑名单/白名单应用。
- 如果启用了稀有度门槛但无法判断稀有度，该钥匙会被丢弃。

```yaml
# 只保留稀有钥匙，并从中丢弃 armor_breakers / resistance_breakers
Sigils:
  rarity: rare
  blacklist:
    - armor_breakers
    - resistance_breakers
```

钥匙词缀和地点名称使用小写字母，并以下划线代替空格。完整列表见
[assets/lang/enUS/sigils.json](../assets/lang/enUS/sigils.json)。

### 贡品

贡品由顶层键 `Tributes` 定义，使用包含 `name` 和/或 `rarity` 的对象。如果贡品名称出现在 `name`
列表中，**或者**稀有度出现在 `rarity` 列表中，就会被保留。省略某个键表示完全不检查该维度。如果
没有 `Tributes` 筛选器，则保留全部贡品。

无论配置如何，神话贡品始终会被保留。

<details><summary>配置示例</summary>

```yaml
# 只保留 tribute_of_harmony
Tributes:
  name: [tribute_of_harmony]
```

如果非常赶时间，可以省略贡品名称开头的 `tribute_of_`。

```yaml
# 保留 Tribute of Harmony 和 Tribute of Ascendance (Resolute)
Tributes:
  name: [harmony, ascendance_resolute]
```

也可以按稀有度筛选。有效稀有度见 [rarity.py](../src/item/data/rarity.py)。

```yaml
# 只保留传奇和暗金贡品
Tributes:
  rarity: [legendary, unique]
```

同时提供两个键时，只要贡品匹配名称列表或稀有度列表中的**任意一个**就会被保留。

```yaml
# 保留 tribute_of_harmony 以及所有传奇/暗金贡品
Tributes:
  name: [harmony]
  rarity: [legendary, unique]
```

</details>

贡品名称使用小写字母，并以下划线代替空格，同时移除括号。注意，United 和 Resolute 标识符属于
[assets/lang/enUS/tributes.json](../assets/lang/enUS/tributes.json) 中名称的一部分。物品稀有度列表见
[rarity.py](../src/item/data/rarity.py)。

### `GlobalUniques`

查找指定暗金物品时，请使用[词缀章节](#affixes)中的 `uniqueAspect`。如果还希望按特定属性保留其他
暗金物品，请使用 `GlobalUniques`。

全局暗金筛选器由顶层键 `GlobalUniques` 定义，其中包含筛选参数列表。如果没有全局暗金筛选器，或者
物品不匹配任何暗金筛选器（包括词缀规则），则按 `handle_uniques` 配置处理暗金物品。无论任何筛选器
或配置如何，所有神话暗金都会被标记为收藏。

可用的全局筛选条件：

- `minGreaterAffixCount`：只保留至少具有指定数量强力词缀的暗金物品
- `minPercentOfAspect`：只保留独有威能达到总取值范围指定百分比以上的暗金物品。例如设为 80，
  范围为 100-200 时保留 180，150 会被标记为垃圾。数值越小越好的情况也会自动处理。
- `minPower`：要保留的暗金物品最低物品强度
- `profileAlias`：视觉模式中，暗金会显示为 `<文件名>.<威能>`。例如 `myuniques.yaml` 定义了
  `fists_of_fate`，会显示为 `myuniques.fists_of_fate`。可使用威能级别的 `profileAlias` 标志配置
  文件名标签，参见示例。

<details><summary>配置示例</summary>

```yaml
# 保留所有物品强度大于 900 的暗金
GlobalUniques:
  - minPower: 900
```

```yaml
# 保留所有至少有 1 条强力词缀的暗金；日志/视觉模式显示为 cool_stuff.<暗金名称>
GlobalUniques:
  - minGreaterAffixCount: 1
    profileAlias: cool_stuff
```

```yaml
# 暗金匹配任意一条筛选器就会被保留，每个 - 表示一条新筛选器。
# 下例保留有两条强力词缀，或者独有威能百分比大于 80 的所有暗金。
GlobalUniques:
  - minGreaterAffixCount: 2
  - minPercentOfAspect: 80
```

```yaml
# 相反，下例要求暗金同时有两条强力词缀，并且独有威能百分比大于 80
GlobalUniques:
  - minGreaterAffixCount: 2
    minPercentOfAspect: 80
```

</details>

## 巅峰浮层

![示例](../assets/paragon_overlay.jpg)

D4LF 可以从受支持的 Build 规划网站导入巅峰盘，并通过巅峰浮层显示在游戏画面上。

**使用方法**

1. 从受支持的规划网站（Mobalytics / Maxroll / D4Builds）导入 Build。
1. 在导入器中启用**导入巅峰盘**。巅峰数据会存入 Profile 文件夹（默认
   `~/.d4lf/profiles`）中的 Profile YAML。
1. 使用快捷键切换巅峰浮层（默认 **F10**，可在“高级选项”中修改）。
1. 按屏幕提示缩放浮层，直到尺寸合适。理想情况下，金色轮廓应与巅峰盘中的红线大小一致。浮层位置会
   自动保存。

**提示**

- 独占全屏模式可能无法显示浮层；如果浮层未出现，请使用**无边框窗口**模式。
- Build 规划网站可能随时改版。如果导入或导出失效，请提交错误报告。
- InfinityBuilds 导入目前不支持巅峰盘。

## 信息面板浮层

![示例](../assets/readme/infopanel_vert.png)
![示例](../assets/readme/infopanel_hort.png)

信息面板可实时跟踪世界事件，以及本次游戏中的金币和经验统计。

**使用方法**

1. 使用快捷键切换浮层（默认 **F6**，可在“高级选项”中修改）。
1. **移动：** 点击并拖动浮层到所需位置。
1. **设置：** 右键点击浮层任意位置，打开上下文菜单。
1. **锁定：** 放置完成后，在右键菜单中选择**锁定位置**，避免意外移动。

![示例](../assets/readme/infopanel_menu.png)

**功能与设置（右键菜单）**

- **显示开关：** 直接显示或隐藏**世界首领**、**军团集结**和**地狱狂潮**计时器。
- **计时器：**
  - 计时器会自动与 [Helltides.com](https://helltides.com) 同步。
  - **世界首领与军团集结：** 倒计时为绿色，最后 5 分钟闪烁橙色。
  - **地狱狂潮：**
    - 进行期间计时器为黄色，最后 5 分钟闪烁橙色。
    - 距离下一场地狱狂潮的间歇期为绿色，最后 1 分钟闪烁橙色。
- **金币设置（子菜单）：**
  - **跟踪金币：** 启用或停用金币跟踪的总开关；关闭后其他金币选项会变灰。
  - **显示每小时金币：** 显示本次游戏计算出的每小时金币收入。
  - **显示获得金币：** 显示上次重置后累计获得的金币。
- **经验设置（子菜单）：**
  - **跟踪经验：** 启用或停用经验跟踪的总开关；关闭后其他经验选项会变灰。
  - **显示每小时经验：** 显示计算出的每小时经验。
  - **显示获得经验：** 显示上次重置后累计获得的经验。
  - **显示升级所需时间：** 根据当前每小时经验估算距离下一级的剩余时间。
  - **显示下次扫描：** 显示距离下一次自动经验检查的剩余冷却时间。
  - **打开背包时自动采集经验：** 启用后，每次打开背包，工具都会自动将鼠标悬停到经验条上扫描数值。
  - **经验采集间隔（子菜单）：** 设置自动扫描冷却时间，例如“从不”、`0m`、`3m`。
  - **配置经验条位置：** 在屏幕上的经验条周围拖动方框完成校准。
  - **重置经验条位置：** 将自定义经验条位置恢复为默认值。
- **重置统计（子菜单）：**
  - **重置金币：** 清除本次游戏金币数据并设置新基线。
  - **重置经验：** 清除本次游戏经验数据。
- **界面调整：**
  - **方向：** 在**水平**与**垂直**布局之间切换。
  - **增大/减小尺寸：** 调整浮层字体大小和整体缩放。
- **字体（子菜单）：**
  - 选择浮层文字所用的字体。
- **系统：**
  - **立即刷新计时器：** 强制从网络刷新事件数据。
  - **锁定位置：** 禁用拖动，让浮层保持固定。
  - **关闭浮层：** 关闭信息面板浮层。

**经验条位置建议**

建议按下图配置经验条位置，这个位置通常最容易稳定采集数据。

![示例](../assets/readme/infopanel_expbar.png)

**跟踪逻辑**

- 浮层通过游戏的文字转语音（TTS）系统采集数据。
- **金币跟踪：**
  - 打开“跟踪金币”，再打开背包即可初始化。
  - 内置验证逻辑会忽略物品说明中短暂出现的“售价”文本。
- **经验跟踪：**
  - 将鼠标悬停在游戏内经验条上即可初始化。
  - **自动扫描：** 如果设置中启用“打开背包时采集经验”，每次打开背包时，浮层都会自动将鼠标移动
    到经验条上扫描更新。
  - **冷却时间：** “经验采集间隔”控制自动扫描频率，避免过度移动鼠标。

## 后续计划

- 制作初始设置视频
- 完善 GUI 文档
- 想要未列出的功能？请提交 GitHub Issue，或自行修改后提交 PR。

## 高级用户信息

大多数用户不需要了解以下内容，但为了方便希望深入了解 D4LF 工作方式的用户，仍保留在这里。

### 配置文件

`C:/Users/<WINDOWS_USER>/.d4lf` 中的配置文件夹包含：

- **profiles/\*.yaml**：决定要筛选哪些物品。GUI 创建的 Profile 会自动放在这里。
- **params.ini**：包含快捷键、需要检查的储物箱页数等设置。请通过 GUI 设置窗口管理此文件。

通常无需手动修改这些文件，但在排查异常错误时，了解它们的位置可能很有用。

## 开发

### 使用 uv 设置开发环境

如需提交 PR，请先在当前仓库页面创建自己的 fork，然后克隆该 fork。

开始前请[安装 uv](https://docs.astral.sh/uv/getting-started/installation/#winget)。

```bash
git clone https://github.com/<YOUR_ACCOUNT>/<YOUR_FORK>.git
cd d4lf
uv sync
uv run python -m src.main
```

#### 非 Windows 开发模式（macOS/Linux）

可以在 macOS/Linux 上运行 GUI 进行开发：

```bash
uv run python -m src.main
```

在非 Windows 平台上，D4LF 会自动以**仅 GUI 模式**启动。可以使用 GUI 和编辑设置/Profile，但依赖
Windows API 的运行时功能会被禁用，包括 TTS 管道连接、Diablo 窗口检测、浮层、快捷键和自动化。

如果看到缺少 Visual Studio 代码的错误，请打开错误中提供的链接。使用默认选项安装 Visual Studio
Build Tools 2022，并额外选择“MSVC VS 2022 C++ ...”和“Windows 11 SDK ...”。重启终端后重试。

以下 Stack Overflow 页面介绍了保持主分支最新和提交 PR 的标准流程：
https://stackoverflow.com/questions/20956154/whats-the-workflow-to-contribute-to-an-open-source-project-using-git-pull-reque

### 格式化与代码检查

使用 [prek](https://prek.j178.dev/)。

运行：

```bash
prek run -a
```

如需在每次 push 前自动运行 prek，可安装 Git hook：

```bash
uvx prek install --hook-type pre-push
```

此后每次 push 都会自动运行项目的 pre-commit 检查。

### 关于使用 AI 提交 PR

D4LF 不禁止使用 AI，但需要注意：

- 你需要对提交的每个 PR 负责。
  - 应当测试自己的代码
  - 应当修复自己的工作导致的错误
  - 必须理解自己修改了什么以及为什么这样修改
- PR 应只修改实现新功能所必需的代码，改动越少越好。
- 除非删除相关代码，否则应保留现有代码注释。
- 每项功能应单独提交一个 PR，并尽量保持 PR 较小。发布说明根据 PR 标题生成；如果一个 PR 包含
  太多内容，发布说明就无法准确描述。
- 请做好收到大量 PR 评论的准备。维护者必须理解所有改动，因为几个月后出问题时需要由维护者修复。

请理解，D4LF 目前只有一位全职维护者，而且该维护者不使用 AI。代码必须保持人类可读，项目最初也是
由人类编写。如果 AI 与人类意见不一致，以人类判断为准。AI 可以提供帮助，但也可能犯下非常明显的
错误。

## 支持项目

支持本中文分支最好的方式，是把它分享给朋友和社区，并在本仓库提交可复现的问题报告。程序右上角的
Discord 按钮和 [Ko-fi](https://ko-fi.com/d4lf) 均属于上游 `d4lfteam/d4lf` 项目；Ko-fi 款项直接交给
上游维护者，与本中文分支发布者无关。

## 致谢

- 图标基于 [CarbotAnimations](https://www.youtube.com/carbotanimations/about) 的作品
- 部分 OCR 代码最初来自 [@gleed](https://github.com/aliig)，感谢他的贡献
- 用于匹配的名称和纹理来自 [Blizzard](https://www.blizzard.com)
- 感谢 NekrosStratia 提供最初构想并协助实现 TTS 模式
