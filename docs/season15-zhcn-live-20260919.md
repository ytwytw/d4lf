# Season 15 简中本机实测 — 2026-09-19

## 结论与证据边界

本轮实际运行的是本机原生《暗黑破坏神 IV》和打包后的 `d4lf/d4lf.exe`，不是 Moonlight，也不是只运行离线解析测试。
已查看角色穿戴装备、背包装备、神符、赫拉迪姆封印、贡品及梦魇符印。
第一轮 fast 模式的 **14 个真实 TTS 样本中，13 个正常解析，1 个贡品真实失败**；不能将这轮写成全部通过。
随后使用独立、单规则的高亮配置，实际确认了背包靴子的正例、已装备头盔的负例以及空格清除。
补充可靠译名并重启 EXE 后，同一个“次级和谐贡品”在 11:02:48 实机复测成功；初始失败记录仍保留。
最后重建的 r4 EXE 再次通过装备／贡品正反例与空格清除，并通过导入窗口“明确失败提示 → 有效链接成功”的现场复测。
这不等于用户现有 build 的匹配正确，也不等于自动标记、丢弃或整理装备已测试。

本报告按轮次保留 `2026-09-19` 的初始失败和后续复测（America/Toronto，UTC−04:00）。
日志文件名用 UTC，日志内容用本机时间；例如 `14_45_29.log` 内是 `10:45:29`。
程序自报版本为 `v10.0.3+zhcn.1`，检查时源码提交基线为 `f5379fc89a58691533ad7659b9ae3537d8c289dd`。
当天新发现的上游 `v10.0.4` 和随后修改的贡品目录，不自动包含在本轮首次启动的旧打包程序中。

证据位于本机工作区，以下 `.scratch/` 和运行日志不保证包含在 Git 仓库或发行包内：

- fast 原始日志：`d4lf/logs/log_2026_09_19_14_45_29.log`；本轮结束时复制件为 `.scratch/smoke-20260919/frozen/app.log`。
- 高亮原始日志：`d4lf/logs/log_2026_09_19_14_53_38.log`。
- 现场截图：`.scratch/smoke-20260919/frozen/`，下文按文件名索引。
- 检测到的游戏窗口为 `3840×2160`；保存的 JPG 是缩放后的截图，不是另一种已测游戏分辨率。
- 下表逐项核对原始 TTS 与解析对象的过滤相关身份、数值和范围。出售价格、耐久度、操作提示等不作为过滤词缀；完整原文及完整对象保留在上述日志。

## 第一轮：fast 读取与解析

### 隔离配置，没有载入用户规则

仅子进程的用户目录指向 `.scratch/frozen-review-user`，没有修改真实用户的 `params.ini`。
该目录下 `.d4lf/params.ini` 内容为：

```ini
[general]
language = zhCN
vision_mode_type = fast
run_vision_mode_on_startup = True
handle_uniques = ignore
profiles =

[advanced_options]
vision_mode_only = True
log_lvl = debug
```

启动日志明确告警 `No profiles are currently loaded`。因此装备部分验证的是实际游戏 → TTS → 中文解析链路，
不是用户 build 的 keep/junk 正确性。无 profile 时部分符印、贡品仍按内置默认行为记录 `Matched Sigils` 或
`Matched Tributes`，也不能把这些日志解释为自定义规则已经生效。

### 全部 14 个真实样本

范围记法为 `当前值 [最小值–最大值]`；`—` 表示原始文本未提供，不代表数值为零。
表中的英文名是程序规范 ID，不是重新给游戏物品编造译名。

| 时间；Raw/Parsed 日志行 | 实际中文样本                   | 解析身份                                      | Raw 与 Parsed 的逐项核对                                                                                                                                                                                                                                                 | 现场截图                      |
| ----------------------- | ------------------------------ | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| 10:45:59；15/16         | 唤魔师的顶盔，已装备           | `Helm / Rare / 810`                           | `maximum_life=726 [541–740]`；`wrath_regeneration=3 [3–4]`；`lightning_resistance=1604 [1600–1799]`；`impairment_reduction=5.4 [5–8]`。原文基础护甲 1215 不误作额外护甲词缀。                                                                                            | `equipped-helm.jpg`           |
| 10:46:25；17/18         | 乔丹之石，已装备               | `Ring / Unique / 824`；`stone_of_jordan`      | `willpower=78 [69–83]`；`maximum_life=986 [741–1000]`；`wrath_every_kills=2 [1–2]`（没有误取“每10次击杀”的 10）；`to_all_skills=2 [1–2]`。暗金威能 `stone_of_jordan=15 [15–25]`。基础所有抗性 114 不误作词缀。                                                           | `stone-of-jordan.jpg`         |
| 10:46:42；19/20         | 寻觅者的黎明，背包             | `Boots / Rare / 850`                          | `armor=971 [780–980]`；`impairment_reduction=7.6 [5–8]`；`dodge_chance=6.7 [6–7]`；`attacks_reduce_evades_cooldown_by_seconds=1.1 [1–1.2]`。基础护甲 638 及比较提示 `+0.2% 坚韧` 没有挤入词缀结果。                                                                      | `backpack-boots-clear.jpg`    |
| 10:46:53；21/22         | 剥削者的骨织裙甲，已装备       | `Legs / Legendary / 845`                      | `willpower=76 [69–83]`；`maximum_life=785 [741–1000]`；`life_regeneration=100 [78–106]`；`armor=1527 [1378–1560]`。基础护甲 1584 不误作额外词缀。传奇威能识别为 `exploiters`，全文保留控制时间 `50%` 和不可阻挡增伤 `45% [30–45]`；威能结构化数值为 `None`，原因见下节。 | `equipped-pants.jpg`          |
| 10:47:08；23/24         | 飘忽威胁之狩猎奖章，已装备     | `Amulet / Legendary / 723`                    | `willpower=82 [70–84]`；`armor=644 [611–688]`；`lightning_resistance=1492 [1420–1599]`；`resource_cost_reduction=2.8 [2–4]`。威能 `of_elusive_menace` 全文中的躲闪 `33% [30–38]` 保留，结构化数值为 `None`。基础所有抗性 134 不误作词缀。                                | `equipped-amulet.jpg`         |
| 10:47:51；25/26         | 工匠之魔性的神符               | `Charm / Rare / 201`                          | `to_demonology_skills=1 [1–2]`；`crafting_material_drop_rate=2.2 [1.9–2.8]`。                                                                                                                                                                                            | `crafting-material-charm.jpg` |
| 10:48:03；27/28         | 至臻之和谐赫拉迪姆封印，已装备 | `HoradricSeal / Rare / 815`                   | 固有 `charm_slot=4`；`all_stats=4.5 [4.5–6]`；`mastery_to_all_skills=1`，原文没有范围，所以 `min/max=None` 正确。                                                                                                                                                        | `equipped-seal.jpg`           |
| 10:48:18；29/30         | 霍拉松的锁链之弗巴             | `Charm / Set / 850`；套装 `chains_of_horazon` | `poison_resistance=2085 [1800–2274]`；`total_armor=7 [6.5–8]`。套装身份正确；套装成员清单、2/3/5 件效果及故事文本没有被误认作额外词缀。本例没有验证套装规则命中。                                                                                                        | `set-charm.jpg`               |
| 10:48:31；31/32         | 愤怒之娴熟赫拉迪姆封印，背包   | `HoradricSeal / Rare / 850`                   | 固有 `charm_slot=4`；`critical_strike_chance=9 [7.5–10]`；`chains_of_horazon_maximum_wrath=6 [5–11]`。                                                                                                                                                                   | `backpack-seal.jpg`           |
| 10:48:55；33/34         | 赘生物供品 (3)                 | `Tribute / Magic`；`tribute_of_growth`        | 叠加数量 `(3)` 不妨碍名称识别；“达到调谐级别1可获得经验值”与 growth 奖励含义一致；贡品没有装备词缀或物品强度，结果 `affixes=[] / power=None`。                                                                                                                           | `growth-tribute.jpg`          |
| 10:49:06；36/37         | 梦魇符印：水手避难所           | `Sigil`；`mariners_refuge`                    | 地下城探险 → `dungeon_delve`；火山 → `volcanic`。规则推导 `Common`，不是从原文猜测品质。                                                                                                                                                                                 | `mariners-sigil.jpg`          |
| 10:49:21；39/40–46      | 次级和谐贡品                   | **解析失败，没有 Parsed Item**                | 原始文本明确 `魔法次级和谐贡品`、奖励升级“次级符文”、调谐级别1可获得符文。抛出 `ValueError: Could not resolve tribute name: 次级和谐贡品`。不能因 TTS 有原文就写成解析成功。                                                                                             | `lesser-harmony-before.jpg`   |
| 10:50:02；47/48         | 梦魇符印：喂食之地             | `Sigil`；`feeding_grounds`                    | 引导圣坛 → `channeling_shrines`；躁狂猎手 → `hunters`。规则推导 `Magic`。                                                                                                                                                                                                | `feeding-ground-sigil.jpg`    |
| 10:50:17；50/51         | 梦魇符印：浩劫                 | `Sigil`；`cataclysm`                          | 地下城探险 → `dungeon_delve`；风暴灾星之怒 → `stormbanes_wrath`。规则推导 `Common`。                                                                                                                                                                                     | `cataclysm-sigil.jpg`         |

所有成功样本均未被错误识别为商店物品或先祖物品；本轮没有对应正例，不能据此宣称这些属性的检测已完整测试。
三个符印的品质来源为 `SigilRules`；游戏 TTS 未直接给品质，所以上表不是三次“品质文本识别”测试。

### 传奇威能 `value=None` 不是本次中文回归

`src/perception/parser/details.py` 明确分开两条路径：

- 暗金 `_get_aspect_from_text()` 从描述中解析 `value/min_value/max_value`，乔丹之石实际验证了 `15 [15–25]`。
- 传奇 `_get_aspect_from_name()` 只解析名称并保留完整 `text`，不解析 roll 数值。因此 `exploiters` 的 45% 留在文本中，但三个数值字段为 `None`。

这与 README 的 `AspectUpgrades` 设计和 `src/item/filter/equipment.py` 的传奇名称／法典升级判断一致。
现有 profile 的数值阈值模型针对暗金威能，并不支持普通传奇威能 roll 筛选。
因此不能据此报告“45%丢失导致中文解析错误”，也不能宣称本次已经验证“按传奇威能45%阈值过滤”。
普通传奇威能数值筛选是明确的功能边界；若要支持，需单独设计多数字描述的取值规则。

## 初始失败与告警必须保留

| 问题                                 | 实际证据                                                                                                 | 本轮处理／边界                                                                                                |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 次级和谐贡品未收录                   | fast 日志 10:49:21 的异常；原始 TTS 和 `lesser-harmony-before.jpg`                                       | 已补充经实际客户端证明的译名；更新外置目录、重启 EXE 后于 11:02:48 对同一物品实机复测成功，详见下节。         |
| 自动更新端点 404                     | 10:45:34 对 `repos/ytwytw/d4lf/releases/latest` 的 HTTP404，随后跳过检查                                 | 是实际发行／更新服务缺口，不是装备解析失败，也不是上游“没有更新”的证据。本轮没有发布 release 或修正远端状态。 |
| 无 profile                           | 10:45:32 明确告警                                                                                        | 初始隔离配置故意空置；限制的是测试结论，不是本轮修复的缺陷。                                                  |
| 找不到游戏 LocalPrefs                | 两轮启动均有告警                                                                                         | 子进程用户目录隔离后，不包含真实游戏的 Documents。真实路径文件仍在；不能据此断言用户未配置读屏。              |
| Large 字体属于已声明不支持的高亮配置 | 实际 `Documents/Diablo IV/LocalPrefs.txt` 第51行 `FontScale "2"`，10:44:54 保存；代码对 Large 有明确提示 | 本轮不改游戏字体。后续两个实测高亮样本成功，只算该环境的局部观察，不能消除支持范围限制。                      |

两轮启动均确认 `C:\Program Files (x86)\Diablo IV\saapi64.dll` 存在且本地签名有效。
没有修改证书、系统安全设置、签名或游戏 DLL。实际读屏设置文件中 `UseScreenReader` 与 `UseThirdPartyReader` 均为 `1`。

## 第二轮：独立单规则的真实高亮正负例

### 配置与离线预检

仅为 EXE 子进程设置用户目录 `.scratch/smoke-20260919/highlight-user`。
实际配置位于其 `.d4lf/params.ini`，profile 为 `.d4lf/profiles/smoke_boots_armor_900.yaml`。
真实用户配置、现有 build 文件和游戏字体均未修改。

```ini
[general]
language = zhCN
vision_mode_type = highlight_matches
run_vision_mode_on_startup = True
profiles = smoke_boots_armor_900
mark_as_favorite = False
auto_use_temper_manuals = False
keep_aspects = none
handle_uniques = ignore
handle_cosmetics = ignore
filter_equipment = True
filter_sigils = False
filter_tributes = False
filter_seals = False
filter_charms = False

[advanced_options]
vision_mode_only = True
log_lvl = debug
show_diagnostics_page = True
```

```yaml
Affixes:
  - SmokeBootsArmor900:
      itemType: boots
      rarity: rare
      minPower: 800
      affixPool:
        - count:
            - name: armor
              value: 900
          minCount: 1
```

先在独立用户目录中用实际配置加载器、`Filter` 与第一轮真实 Raw TTS 做离线预检，进程退出码为0、无 profile 加载错误：

- 靴子850 → `keep=True`，`matched_affixes` 唯一条目为 `armor=971 [780–980]`。
- 头盔810 → `keep=False`，`matched=[]`。

这是配置可加载和阈值语义的验证；真正的屏幕标记由下面的实机证据单独证明。
`vision_mode_only=True` 禁用过滤／转移等自动操作热键，本轮仅悬停观察，不运行收藏、垃圾标记、丢弃或转移操作。
显示诊断页不等于已经开始或完成所有输入事件的审计，因此也不据此声称存在全程输入拦截记录。

### 打包 EXE 的实际结果

| 场景                 | 日志证据                                                                                                                     | 截图直接可见结果                                                                                                                           | 结论                                     |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| 背包靴子正例         | 10:53:40 载入 `smoke_boots_armor_900`；10:54:14 Raw/Parsed 与第一轮一致；10:54:15 `Matched ...SmokeBootsArmor900: ['armor']` | `large-font-highlight-boots.jpg`：绿色外框、底部规则名；唯一绿色方块准确位于 `+971 护甲值` 的 bullet，没有标在7.6%、6.7%或闪避冷却词缀上。 | 该样本的实际过滤命中及词缀标记位置通过。 |
| 切换到已装备头盔负例 | 10:54:56 Raw/Parsed 与第一轮一致；离线同规则不匹配                                                                           | `highlight-helm-negative.jpg`：红色外框，没有绿色词缀方块，也没有保留靴子的绿色规则标记。                                                  | 该次正例 → 不同槽位负例的切换通过。      |
| 再悬停背包空格       | 只移动鼠标，无物品操作                                                                                                       | `highlight-empty-clear.jpg`：物品提示、红框和所有绿色标记均清除。                                                                          | 本次负例 → 空格切换通过。                |

上述两张截图由主任务现场获取，本报告另行打开已保存图片进行复核，没有仅凭 `Matched` 日志推断图形结果。
实际保留了 Large 字体、3840×2160 游戏窗口。**只能报告这两件物品在这套环境成功，不能报告 Large 字体全面支持。**
本轮未测试 Small/Medium、其他分辨率或高 DPI 组合，也没有测试未知新物品在同一槽位替换旧物品时的实机清除行为。

## 第三轮：贡品修复后的同物品实机复测

证据来源、英文身份与真实中文文本的配对详见[同日上游核验](season15-zhcn-upstream-20260919.md)。
采用 `tributes:lesser_tribute_of_harmony` → `次级和谐贡品`，未自行翻译其他 Greater/Lesser 名称。
初始失败的 20 行物品 TTS 已保存为 `tests/perception/data/zhcn_live_tributes.json`，不含玩家信息。
修复前的定向回归复现错误；修复后的解析／目录／来源测试通过。自动测试和真实游戏结果分开记录，不能互相替代。

这一轮还没有改 Python 运行逻辑，因此先正常关闭旧进程，再备份和替换打包目录中的
`tributes.json`、`manifest.json`、`quality-report.json`，逐字节核对与源码一致后重启。
EXE 的 SHA-256 仍为 `77e55160670721d2d4487fa092963ca58a31d2b1519a32f460e9f5d5648d7ffb`。
实测所用 `tributes.json` 的 SHA-256 为 `984ffe4ab310edf11afd96df7b030e6fac3f1646d4758d92e623f97d5df7b987`。
外置 JSON 从 EXE 所在目录加载，不把仍运行中的旧目录缓存误当作新数据。

新日志为 `d4lf/logs/log_2026_09_19_15_02_07.log`，退出后复制到
`.scratch/smoke-20260919/frozen/tribute-retest-app.log`：

- `11:02:48.259`：再次读取同一物品的 20 行 Raw TTS，名称、魔法品质和次级符文奖励均与失败样本相同。
- `11:02:48.260`：产生 `ItemType.Tribute`、`ItemRarity.Magic`、`name='lesser_tribute_of_harmony'`，无解析异常。
- `11:02:48.270`：记录 `Matched Tributes`；现场 `lesser-harmony-after.jpg` 可见绿色“未过滤贡品”标签。

此轮仍使用第一轮的空 profile、fast 隔离配置；绿色标签是默认未过滤策略，不是用户 build 匹配结论。
关闭背包后提示清除，角色留在城镇。三个测试进程均经窗口正常关闭，退出码均为 0，stdout/stderr 为空。
11:04 复查真实 `params.ini` 的 SHA-256 仍为测试前的
`0F3690011C012F59B1AF94D4B812F50E892B81290F26911927B08D193895D855`，没有改用户配置。

## 提交前增量回归与最终包

提交前完整回归另发现线上 Maxroll 返回缺失 `explicits` 的物品，首次结果为
`1 failed, 1394 passed, 19 skipped in 63.98s`。该导入缺陷与真实游戏贡品解析是两条独立链路，不能隐藏失败。
完整 pytest 包含在线导入检查，并非全部离线；只有保存 TTS 样本后的解析／过滤回放是离线回归。
发布工作流原先误标的 `Run offline regression suite` 已更名为 `Run regression suite (excluding Selenium)`，命令及门禁不变。
后续修复、完整回归、重新构建及最终包实机验收结果由本节的追加记录明确标识，不以第三轮旧 EXE 代替最终包验收。

修复后的完整 `uv run --frozen pytest -q` 已退出 0：**1455 passed, 19 skipped in 48.02s**，
命令墙钟 53.733 秒，日志为 `.scratch/smoke-20260919/full-pytest-fixed.log`。
19 个跳过项不是通过项。新增 Maxroll 全目录测试单独运行 89 项通过，其中包含 3 项在线身份选择验证；数量与全套有重叠，不相加。

### Maxroll 的实际来源缺陷与保守处理

9 月 19 日的召唤死灵攻略指向 planner `iz19bx0q` 的第 5 个可见方案，但该 planner 当时只有 3 个可见方案。
旧逻辑把失效的可见序号直接当作原始数组序号，误入隐藏方案。该方案中的部分普通装备只有 id、power 和 name，
没有 `explicits`，最终产生 `KeyError`。另外，`Runeword_Enigma` 有词缀数据，但不是目录中支持的普通暗金身份。

修复范围限定为 Maxroll 导入：

- 缺失／畸形的词缀列表明确告警并跳过该物品；不把缺损数据替换为空列表后生成宽泛筛选条件。
- 不支持的符文之语和未知暗金不降级为普通词缀规则；已知暗金显式提供 `explicits=[]` 时仍允许按名称导入。
- 失效可见序号、隐藏 active profile、非法显式选择、无可见方案均明确失败，不进入保存步骤。
- 用户明确选择当前可见方案时，以该稳定选择为准；新增在线验证实际导入的身份与所选身份一致，并确认只保存一个方案。

失效的默认攻略链接仍需在导入界面选择当前可见方案，或使用有效的 planner 方案链接。
这是防止导入错误流派的明确限制，不宣称旧失效链接已经自动修复。

### JSON 校验在干净检出和重新生成后的稳定性

发现原有运行目录 JSON 在 Windows 为 CRLF，而 Git 保存为 LF，导致 manifest 原始字节哈希在干净检出后失配。
将受哈希约束的文件明确设置为 LF，并更新对应哈希；规范化前后 JSON 语义相同。
数据生成器的 10 个写入点也统一使用 UTF-8/LF 输出，避免 Windows 再次生成 CRLF。
修改前已复现 6 个换行输出断言失败；修复后相关目录、解析、生成器和来源测试 101 项通过。
另从待提交索引分别以 `core.autocrlf=true` 和 `false` 检出到两个新隔离目录：两种模式均为
17/17 个 JSON 与当前文件逐字节相同、17/17 为 LF、15/15 个清单／来源／样本哈希匹配；索引本身前后未变。
这验证的是两种 Git 检出策略的字节稳定性，不是声称在另一台 Linux 机器完成了全部应用测试。

### 第四轮：r3 重建包的真实游戏与导入界面

使用 `uv run --frozen python build.py` 重建（退出码0），不是继续用第三轮旧 EXE。
包在首次启动前生成，独立解包检查 127 个文件、31 个 JSON；资源、README、许可证与源码逐字节一致，
不含测试日志、私人截图或启动后产生的缓存。仅构建子进程收窄 PATH，未更改系统 PATH。

- EXE：`d4lf/d4lf.exe`，136349620 字节，SHA-256 `5bc8f527d50dce43d9446c7e864828ab8a2667b2b30ebd6b1a6d65dc9c90bee0`。
- ZIP：`.scratch/d4lf_v10.0.3+zhcn.1-review-r3.zip`，138577886 字节，SHA-256 `64678568d5f784329f5107d34315f9f962ab4af7bef2b6c84e729eff5769e250`。
- 日志：`d4lf/logs/log_2026_09_19_15_21_08.log`。
- 隔离用户目录：`.scratch/smoke-20260919/final-user`。配置沿用第二轮安全限制，但启用贡品过滤，
  profile `smoke_boots_and_harmony` 同时包含靴子规则和 `Tributes.name: [lesser_tribute_of_harmony]`。

启动时实际游戏显示“网络连接已中断”，现场证据为 `final-start-disconnect.jpg`。
确认信息提示后返回角色页，重新进入同一个已有角色的城镇；没有重新认证或创建、删除、切换角色。
11:21:32 日志确认 TTS 连接，随后同一 EXE 进程收到重入世界后的物品文本。
这是一次实际重入成功的观察；掉线原因未确定，不据此宣称已完成掉线恢复压力测试。

| 实机场景         | 日志与画面结果                                                                                                                                 | 本机截图                  |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| 背包靴子正例     | 11:22:43 正确解析850靴子和护甲971；11:22:44 命中 `SmokeBootsArmor900`，绿色框及唯一护甲词缀方块正确。                                          | `r3-boots-positive.jpg`   |
| 已装备头盔负例   | 正确解析810头盔及四条词缀；画面红框，没有旧靴子绿色词缀方块或规则名。                                                                          | `r3-helm-negative.jpg`    |
| 次级和谐贡品正例 | 11:23:47 解析 `lesser_tribute_of_harmony`；11:23:49 命中明确的贡品名称白名单，画面绿框和 profile 名。此轮不再是空 profile 的默认“未过滤”结果。 | `r3-harmony-positive.jpg` |
| 背包空格         | 贡品提示、绿色框和 profile 名清除。                                                                                                            | `r3-empty-clear.jpg`      |
| 赘生物供品负例   | 11:28:08 解析 `tribute_of_growth`，没有命中和谐贡品白名单；画面红框，无残留绿色规则名。                                                        | `r3-growth-negative.jpg`  |

以上通过的是本机真实游戏的受控正反例；保持 Large 字体及3840×2160，不扩大为其他显示环境的支持承诺。
测试后收起背包，角色留在城镇，未点击、装备、拆分、标记、转移或消耗物品。

同一 r3 EXE 的 GUI 导入测试又发现一个必须保留的失败：默认召唤死灵攻略链接被安全拒绝，
隔离 profiles 目录仍只有原来的 smoke profile，没有保存隐藏方案；但主窗口有错误日志，
导入窗口却只显示两行 `Loading`，生成按钮恢复可点，没有明确失败提示或对话框。
截图为 `r3-importer-missing-error.jpg`、`r3-importer-main-error.jpg`。
因此 r3 的游戏 smoke 通过不等于整个包验收通过；不能把缺失错误反馈写成成功。

随后在同一导入窗口改用 `https://maxroll.gg/d4/planner/iz19bx0q#1`，界面实际显示创建
`maxroll_necromancer_minion_necromancer_s15_starter.yaml` 和 `Finished`，截图为 `r3-importer-starter-success.jpg`。
主窗口列表新增该方案但没有勾选启用，原 smoke profile 仍是唯一激活项。
r3 经窗口正常关闭，退出码0、stdout/stderr为空，完整日志复制到 `.scratch/smoke-20260919/frozen/r3-app.log`。
退出后真实用户 `params.ini` 的 SHA-256 仍为前文测试前哈希。

### 导入窗口反馈修复与 r4 回归

根据上述真实 GUI 失败，补上后台 worker 到窗口的失败信号：已知来源错误直接在导入窗口日志中显示，
三个路径（直接导入、发现可选方案、选择后保存）均连接失败反馈。
失败后恢复按钮并释放 session，但不发出导入成功信号；下次成功导入可以正常恢复，关闭窗口后忽略迟到反馈。
不修改所有 provider 的重试语义，也不让无效 Maxroll 链接退回隐藏方案。

包含真实 Qt 窗口文本断言和跨线程信号的定向回归25项通过；最终完整
`uv run --frozen pytest -q` 为 **1459 passed, 19 skipped in 70.11s**，退出码0、墙钟75.875秒，
日志 `.scratch/smoke-20260919/full-pytest-feedback-fixed.log`。
这仍不能代替下一轮冻结 EXE 的现场反馈验收。

### 第五轮：r4 最终候选包

r4 再次完整构建并在首次启动前打包；构建、独立解包和校验均退出0。
127 个文件、31 个 JSON，与冻结源码中的 assets、README 和 LICENSE 字节一致。
确认冻结代码包含 GUI 失败信号、窗口失败状态和 Maxroll 选择／物品防护；没有外来 ICU。
发行包隐私扫描无泄露发现，EXE 大于仓库25MiB限制只作为发行二进制的体积说明，不将其提交 Git。
r3 包、运行目录和日志完整保留，未覆盖之前的证据。

- EXE：136349871 字节，SHA-256 `8cba7baef3e143981cd219ac080e3fafd440ca8404d5fcc937e9f72cad80319a`。
- ZIP：`.scratch/d4lf_v10.0.3+zhcn.1-review-r4.zip`，138578501 字节，SHA-256 `4601cc8d63812c7d67792617ca96c139c5110e02e0128d409961809f572927ff`。
- 新隔离用户目录：`.scratch/smoke-20260919/r4-user`，使用与第四轮相同的安全配置和 `smoke_boots_and_harmony` 规则。
- 本轮日志：`d4lf/logs/log_2026_09_19_15_42_30.log`。

#### r4 导入界面现场结果

默认攻略链接在 11:43:54 被安全拒绝，导入窗口明确显示 `Import failed: Maxroll visible profile 5 no longer exists...`，
提示选择当前可见变体或有效 planner 链接。生成按钮恢复，没有 `Finished`，profiles 目录仍只有原 smoke 文件。
证据为 `r4-importer-error-visible.jpg`。这修复了第四轮实际看到的“只有 Loading、没有失败原因”。

在同一窗口将链接改为 `https://maxroll.gg/d4/planner/iz19bx0q#1` 后，11:48:41 成功创建一个 Starter YAML 并显示 `Finished`，
证据为 `r4-importer-starter-success.jpg`。文件的 Name、Source 确认是 Starter／`#1`，不是隐藏方案；
9 条装备规则各有4条词缀、至少命中3条，另有1个 charm 规则组、1个 seal 规则组及4阶段巅峰数据。
这验证导入目标和产物结构，不扩大为所有构筑规则语义的完整认证。

新文件为76819字节，SHA-256 `4123798c8000d1d68d8bf05a860c8f335c6ec1f67b785126728361a302a0296d`。
原 smoke 文件仍251字节，SHA-256 `cfcacc79a49eb9a8cd27afc4271fc59a53a5fc50a13f5e02b48d31148a406481`。
界面与隔离配置均确认只启用 smoke，新导入未激活；证据为 `r4-active-profiles.jpg`。

#### r4 本机真实游戏现场结果

同一个 r4 进程在原生游戏中重新打开背包，逐项悬停而不点击物品：

| 场景             | 日志与画面结果                                                                                  | 本机截图                  |
| ---------------- | ----------------------------------------------------------------------------------------------- | ------------------------- |
| 背包靴子正例     | 11:49:29 解析850靴子、护甲971；11:49:31 命中 `SmokeBootsArmor900`，绿框和唯一护甲词缀方块正确。 | `r4-boots-positive.jpg`   |
| 已装备头盔负例   | 11:49:49 解析810头盔及四条词缀；显示红框，没有旧靴子的绿色词缀方块或规则名。                    | `r4-helm-negative.jpg`    |
| 次级和谐贡品正例 | 11:50:19 解析 `lesser_tribute_of_harmony`；11:50:21 命中贡品名称白名单，绿框及正确 profile 名。 | `r4-harmony-positive.jpg` |
| 背包空格         | 和谐贡品提示、绿框与 profile 名均清除。                                                         | `r4-empty-clear.jpg`      |
| 赘生物供品负例   | 11:50:57 解析 `tribute_of_growth`，未命中白名单；红框，无残留绿色规则名。                       | `r4-growth-negative.jpg`  |

测试结束收起背包，角色仍在城镇；没有操作物品或改变装备状态。r4 经主窗口正常关闭，退出码0，stdout/stderr为空，
没有残留 d4lf 进程。日志保留为 `.scratch/smoke-20260919/frozen/r4-app.log`。
退出后真实用户 `params.ini` 的 SHA-256 仍是测试前的 `0f3690011c012f59b1af94d4b812f50e892b81290f26911927b08d193895d855`。

本轮仍有已知启动提示：尚无正式 GitHub release，因此 latest 端点返回404，自动更新跳过；隔离用户目录没有游戏偏好文件，
自动 TTS 设置检查提示不可用，但 11:42:37 已实际连接 TTS，随后四个游戏物品均收到实时文本。
这些提示没有隐藏，也不宣称正式更新通道已验收。现场截图和完整日志留在本机，不随本次 Git 推送上传。

## 本轮仍未测试，不能作为发布已通过项

- 用户实际选择的 build／profile、整包装备 keep/junk 判断和复杂多规则组合。
- 收藏、垃圾标记、丢弃、分解、出售、转移、自动使用物品等任何会改变装备状态的操作。
- 仓库／商店场景、所有装备槽位、所有暗金／神符／封印，以及 S15 全目录。
- Greater Affix、先祖、神话、法典升级、装备外观升级等未出现的正例与边界。
- 传奇威能数值阈值（现有功能本来就不支持）、真实套装／神符／封印自定义规则命中。
- 同槽位未知物品替换、快速连续切换、反复掉线／重连压力、重开游戏及长时无人值守稳定性；第四轮仅观察到一次实际重入成功。
- 新上游版本集成、所有未确认中文名称、远端更新端点可用性与正式发布下载验证。

本轮是有实际游戏、实际背包与穿戴装备证据的受控 smoke test；不是“所有功能都测过”的发布保证。
