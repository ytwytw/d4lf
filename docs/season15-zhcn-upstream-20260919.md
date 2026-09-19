# Season 15 Upstream Verification — 2026-09-19

## 技术结论：可以准备下一次集成，但本报告不是合入或发布证明

截至 **2026 年 9 月 19 日 14:43:44 UTC** 的只读核验，英文 d4lf 已从 `v10.0.3` 更新到 `v10.0.4`。
新增的 **16 个稳定 ID 中，15 个能从已锁定的英/简中配对数据证明中文文本，1 个 `affixes:resistance` 仍未确认**。
这些译文已经存在于来源快照，并非今天新发布的翻译；之前英文运行目录没有相应稳定 ID，不能提前擅自创建。

本报告以中文分支已提交的 `f5379fc89a58691533ad7659b9ae3537d8c289dd` 为本地比较基线。
**`v10.0.4` 部分仅整理证据，不表示已经合入，也不表示其新增物品已通过实机测试。**
核验后，同日实机在 14:49 UTC 证实原有缺口中的“次级和谐贡品”，随后只修复这一条译名、清单和测试，未改解析代码或来源锁。
原有 13 个未确认贡品因此减至 **12 个**。“恶毒”仍然不能仅凭名字消歧，但本次找到可支持后续按描述消歧的完整双语来源记录。

## 版本变化存在，但 18 份锁定数据文件没有变化

下面的“当前”是上述检查时点，不是持续监控承诺。提交 SHA 指 Git 对象；文件 SHA-256 指 HTTP 返回的原始文件字节，二者不是同一种哈希。

| 来源             | 原基线                                                    | 本次检查结果                                                                                       | 对集成的含义                                                     |
| ---------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| d4lf             | `v10.0.3` / `3ecfe3b506d553fe5981e95fd2256bbbb164e8a4`    | `v10.0.4` / `6561068de4464dc3f2040ef659b206a4ae1e2f4c`，提交时间 `2026-09-18T18:52:43Z`            | 有代码和英文目录增量，需要单独移植与回归。                       |
| d4data           | `33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0`，`3.2.1.73552` | HEAD 与构建均未变；提交时间 `2026-09-16T12:15:33Z`                                                 | 不需要因本次检查更换游戏数据基线。                               |
| Diablo4Companion | `a7efa39819ffec10f2dd1c06e874744d2605167f`                | HEAD 为 `5ac10ca801bec9de9f98481584f1a48ecd8e6c6b`，提交时间 `2026-09-19T11:56:53Z`，领先 5 次提交 | 5 个变更文件均为导入代码/项目版本；10 份已锁定数据文件字节不变。 |
| D2Core           | 构建 `73552`                                              | 站点公开脚本仍声明 `D4_BUILD_VERSION="73552"`；8 份锁定 JSON 全部哈希相同                          | 同构英/中配对仍有效，但不能据此断言站点收录了全部游戏文本。      |

依据：[d4lf 版本比较](https://github.com/d4lfteam/d4lf/compare/v10.0.3...v10.0.4)、
[d4data 固定提交](https://github.com/DiabloTools/d4data/commit/33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0)、
[d4data 在线构建文件](https://raw.githubusercontent.com/DiabloTools/d4data/master/buildVersion.txt)、
[Companion 提交比较](https://github.com/josdemmers/Diablo4Companion/compare/a7efa39819ffec10f2dd1c06e874744d2605167f...5ac10ca801bec9de9f98481584f1a48ecd8e6c6b)、
[D2Core 检查时的公开脚本](https://www.d2core.com/assets/index-BUze7J1p.js)。
动态 HEAD、构建文件及站点脚本将来可能变化；下文保留固定提交和原始字节哈希用于复核。

## 同日实机追加：只修复“次级和谐贡品”这一条现有缺口

2026 年 9 月 19 日 `14:49:21.006 UTC`，本机 `3.2.1.73552` 中文客户端的真实 TTS 触发 `Could not resolve tribute name`。
截图和 TTS 都明确显示物品名称“次级和谐贡品”、类别“魔法次级和谐贡品”、奖励“次级符文”，以及调谐级别 1 可获得符文。
这不是根据 Greater/Lesser 前缀自行推导的翻译。

锁定英文来源同时证明名称和奖励语义：

| 证据对象                                                                                                                                                                                                          | 固定身份                                                                                              | 核对内容                                                                | 原始文件 SHA-256                                                   |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| [英文物品 StringList](https://raw.githubusercontent.com/DiabloTools/d4data/33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0/json/enUS_Text/meta/StringList/Item_X1_Undercity_TributeKeySigil_Runes_MagicOnly.stl.json)    | StringList SNO `2131527`；物品 key `X1_Undercity_TributeKeySigil_Runes_MagicOnly`，物品 SNO `2131528` | 名称为 Lesser Tribute of Harmony；调谐级别 1 的符文奖励、所有难度可用。 | `98de30de3c929748aded93b18b183a29c7c499ce9fee6a19386324137ac075d6` |
| [英文奖励 StringList](https://raw.githubusercontent.com/DiabloTools/d4data/33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0/json/enUS_Text/meta/StringList/DungeonAffix_X1_Undercity_ClearBonus_Runes_MagicOnly.stl.json) | StringList SNO `2131530`                                                                              | 奖励名为 Reward Upgrades: Lesser Runes；同样要求调谐级别 1 或更高。     | `488b809fd409ffccc143eda2a73b8f201565b6575dcca0effcc693e430637d09` |
| [仅含物品文本的实际 TTS 回归样本](../tests/perception/data/zhcn_live_tributes.json)                                                                                                                               | `tributes:lesser_tribute_of_harmony`                                                                  | 20 行物品 TTS；不含玩家名称、账号或截图。                               | `83ee6c29b663ca85033f5d7153b64c19b2f0c151f2f25e43a365fb835125ed21` |

据此采用 `tributes:lesser_tribute_of_harmony` → `次级和谐贡品`，仅更新 `tributes.json`、reviewed overrides、manifest 和质量统计。
回归先复现同一解析错误（8 个实际样本中 1 个失败），修复后相关解析/目录/导入来源测试 **79 项通过**；另加入样本哈希核验后目录测试 **13 项通过**。
此处测试数量有重叠，不相加。Ruff 和 JSON 格式检查通过。冻结 EXE 的再次实机验收由单独的测试记录负责，本节不提前宣称通过。

更新后的统计为 2,741 个已解析来源记录、12 个未确认记录、75 个 reviewed overrides；`runtime_ready` 保持 `false`。
`tributes.json` 在后述 LF 规范化后的 SHA-256 为 `d54daa9774774c0ae37c223c1d675aa475ea32289a1db2ede2cf7e8f1b4d6ebe`。
其余 12 个缺失贡品保持空译文，不猜测；上游 16 个新增 ID 仍然只做证据整理，没有借此合入。

## 跨平台哈希更正：固定已哈希 JSON 的 LF 换行

最后检查发现 Windows 的 `core.autocrlf=true` 与未声明 JSON 换行属性结合，会让同一文件在 Windows/Linux 检出后产生不同字节。
新贡品样本当时为 LF，但重新检出可能变成 CRLF；另外 12 份运行目录 JSON、来源锁和 reviewed overrides 的清单哈希都取自 CRLF 字节，Linux 检出后会失配。
这是可复现的清单完整性缺陷，不是翻译变化。

经授权，`.gitattributes` 明确为 `assets/lang/zhCN/*.json`、`assets/catalog/source-lock.json`、`src/tools/data/reviewed_zhCN.json`
以及新增 `tests/perception/data/zhcn_live_tributes.json` 指定 `text eol=lf`。
机械规范化只替换 CRLF 为 LF；逐文件比较规范化前后的解析 JSON 序列化结果，**17/17 语义完全相同**。
然后仅更新 manifest 中 14 个受影响的文件哈希引用，不修改来源版本、词条、翻译或就绪状态。
新样本哈希不变。原始在线来源数据的 18 个哈希也不变；来源锁文件自身的字节哈希改变不等于锁定来源改变。

同时发现数据生成器的 10 个 JSON 输出原先使用平台默认换行。在本机 Windows 添加原始字节断言后，
先复现 **6 个测试失败**（实际输出包含 `\r\n`），随后统一通过 `common.write_json_file` 使用 UTF-8、`newline="\n"`、
原有排序/缩进和末尾换行，修复后目录、解析及生成器 **96 个测试通过**。
新回归覆盖所有 10 个输出路径，以及包含中文的确定字节输出和重复生成结果。
Git 属性检查确认已哈希文件均指定 `text eol=lf`；这是 Windows 本机回归与 Git 属性核验，不声称已执行 Linux CI。

另外依据本地标签解析和远端 `refs/tags/v10.0.3` 双重核对，将新旧审计文档与 `quality-report.json` 中误记的
d4lf 上游提交元数据更正为 `3ecfe3b506d553fe5981e95fd2256bbbb164e8a4`。此勘误不改变来源锁、翻译或就绪状态。

以下保留机械换行阶段的前后哈希。manifest 行的“后”值是更新其引用字段前的机械阶段快照，quality-report 行是提交标识勘误前快照，
不是这两个文件最终的哈希。

| 文件                                            | 规范化前 SHA-256                                                   | 机械规范化后 SHA-256                                               |
| ----------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `assets/lang/zhCN/affixes.json`                 | `33545ebe9e6a988dd2b6698d812f7fc42dd08fab3df6ca428671b9432e25808b` | `6c8cf64184fca6e541ee0da0f85e74c83d37bc0085645f8cb5affd0410358354` |
| `assets/lang/zhCN/aspects.json`                 | `40c7c75c2fe6a3b5e500e7be2031cfce1a1ed87d363ad4ffcd07535155dae32f` | `09c1c4e0efd9f00ee17d9b8379163f94b33ce150dc4c11cc8a0700714622588a` |
| `assets/lang/zhCN/charms_affixes.json`          | `71329bd32e95f0f44098be3a560e669c2808cc6ae47932fabac5ee63031cf181` | `8727694f7e0cb23406c1a85852a832166aeca642f82512b004f93ed493251ed7` |
| `assets/lang/zhCN/corrections.json`             | `feab8dbb58050f692ae1394e050f48c939052a762347d133fe2051caa8144b71` | `c167aba50f686207bae049e1a9d825c83bcf44e660cd10fc15963dee7b05dbf1` |
| `assets/lang/zhCN/grammar.json`                 | `8da2c5d7cb1e4899e3aa229f4bb01b8f4e753dc14b501864e061780ac58d4bcf` | `cec64663df4986dfcf7a25445ea4c08efd6ea95fe8df6e903f683ba13cc9cb9e` |
| `assets/lang/zhCN/item_types.json`              | `8aff3bb2f6cf6cb544e04fa49949d7e039b6d576d9e095c1a209e4212253858d` | `2213ee24160de96056b8a675bd712c396102f3b3d1c963c7b54133a7c8a9adfb` |
| `assets/lang/zhCN/seals_affixes.json`           | `95fdc66c04346c72f98eec24dac2e9d37cc8f737123365072f186493558e22cc` | `f5fa128f0f7fdb8190ab4f2dba09d4e6671ac97d1bc253817d56da0a46e71817` |
| `assets/lang/zhCN/sets.json`                    | `199834c73550c741e74174509fd689ba7e4e553ac5b9f705bc7eeda742c6c8ce` | `ee0d91a95873ee5c823ee1f9600f25dfc72c8ae48cd3d3e063e034dd5a7af484` |
| `assets/lang/zhCN/sigils.json`                  | `b9673147d4497f72de39f60e0f60ea65f3a7b4ae953f1fcaf971f114adae8ca1` | `1bcb21a2d8aeaf6fcc9b39ff501256314b361a1650c70cb8ff51edf250eb7c39` |
| `assets/lang/zhCN/tooltips.json`                | `e71e8f716c04bfbfe8647ed24084dba05daec123cd06457ea4f44568ca5a93c0` | `109629d62706bb2dcb345d7ff109ec6b6991399f59a215b76b39c7e0a7b30718` |
| `assets/lang/zhCN/tributes.json`                | `984ffe4ab310edf11afd96df7b030e6fac3f1646d4758d92e623f97d5df7b987` | `d54daa9774774c0ae37c223c1d675aa475ea32289a1db2ede2cf7e8f1b4d6ebe` |
| `assets/lang/zhCN/uniques.json`                 | `b5ac8057ec3f701581906f3a65fa10e3c705100877b6e3d8371d17919a0ccfae` | `c2a25c57f8a5d36983322d41b031e3e5c9d24a5724f3d94e0a78d7276191a995` |
| `assets/catalog/source-lock.json`               | `149d5dee3252cf3c78b8c1758f4e2c507a541427f45388bab1fe8885e1a1fa45` | `abdee2e5acb8ab94e1acdd663186b498dddb2299e6fd8538ccb2433fe8f6ee59` |
| `src/tools/data/reviewed_zhCN.json`             | `61d7c1f8c46e0f7193f0d7b9c231943e64d785392ba169128b3782aacab306a3` | `8127f55f04045df8e635377c8160d7453114627b63e40e47d9ecc78f84d33aff` |
| `tests/perception/data/zhcn_live_tributes.json` | `83ee6c29b663ca85033f5d7153b64c19b2f0c151f2f25e43a365fb835125ed21` | `83ee6c29b663ca85033f5d7153b64c19b2f0c151f2f25e43a365fb835125ed21` |
| `assets/lang/zhCN/manifest.json`                | `9d3d51593f4d205416e9e6d11e89568d86ec347e4304df3e752a63ce7b045b49` | `34f0d803e7ac8aecd21860a607d8e76238fc554845bdc89ad6bd7b94b39ccf2b` |
| `assets/lang/zhCN/quality-report.json`          | `6a7598f7ec68d3d3aa2b1ec083d099da159c4a733922c59b057c739caac2b486` | `4a24e03164127b93c1ec468ff9241433f878b2da6e83e36abbf9e36062d683e4` |

## 15 个新增 ID 有可复核的中文对应

统计粒度是 `namespace:stable_id`，分母是 `v10.0.3..v10.0.4` 新增的 10 个装备词缀、2 个符印键和 4 个暗金键。
不是全目录覆盖率，也不是实机成功率。表中 `#` 是来源的数值占位符，不是应显示在游戏中的文字；正式集成还须按现有规则规范化并测试。
来源代号对应文末完整链接和 SHA-256。不同来源的 ID 不能互相直接连接：例如 D2Core 的物品 ID 与 Companion 的威能 ID 不同。

### 九个词缀：按 Companion 的双字段身份连接

下列每行均按 `(IdSno, IdName)` 精确匹配 `C-A-en` 和 `C-A-zh`，每个英文记录只匹配到一个中文记录。
来源将部分同义记录合并为分号分隔字段；保留完整字段，不把字符串当作单个数值 ID。

| 新稳定 ID（`affixes:`）                                     | 来源中文 `Description`                 | `IdSno`           | `IdName`                                                  |
| ----------------------------------------------------------- | -------------------------------------- | ----------------- | --------------------------------------------------------- |
| `bonus_experience`                                          | `+#% 奖励经验值`                       | `2684356`         | `S15_Annihilus_ExperienceBonus`                           |
| `can_equip_more_unique_charm`                               | `可额外装备 # 个暗金神符`              | `2684336`         | `HellfireTorch_ExtraUnique`                               |
| `chance_for_an_extra_item_from_the_purveyor_of_curiosities` | `+#% 几率从珍品商处额外获得一件物品`   | `2678490`         | `Runeword_Gamble_Bonus`                                   |
| `deadly_strike_chance`                                      | `+#% 致命打击几率`                     | `2675623`         | `Runeword_DeadlyStrikeChance`                             |
| `faster_cast_rate`                                          | `+#% 更快施法速度`                     | `2665343`         | `X2_Runeword_CastSpeed_15Percent`                         |
| `lucky_hit_up_to_a_chance_to_deliver_a_crushing_blow`       | `幸运一击: 最多有 #% 几率造成粉碎一击` | `2679332;2679489` | `Runeword_CrushingBlow_20pct;Runeword_CrushingBlow_25pct` |
| `mondays_now_count_as_tuesdays`                             | `现在星期一也算作星期二`               | `2677305`         | `OPAL_INHERENT_Mondays`                                   |
| `primary_resource_on_kill`                                  | `+# 击杀回复主要资源`                  | `2686425`         | `Runeword_Resource_On_Kill_2`                             |
| `to_shout_skills`                                           | `+# 至吼叫技能`                        | `2683405`         | `Runeword_Shout_Skills_5`                                 |

其中 `bonus_experience`、`deadly_strike_chance`、`primary_resource_on_kill`、`to_shout_skills` 还分别得到 `D-A-en`/`D-A-zh` 同 `(id,key)` 记录的佐证，ID/key 与上表一致。
注意 `faster_cast_rate` 不能仅凭内部名称近似推断：D2Core 中另外几个 `Runeword_FasterCastRate_*` 记录的英文实际是 Attack Speed、中文实际是攻击速度；本报告采用的是上表不同且有完整双语对应的 `2665343`。

### 四个暗金：按 D2Core 同构物品身份连接

下面均使用 `D-U-en`/`D-U-zh` 的 `(id,key)` 配对，每行恰好匹配一条中文记录。
这证明物品名称，不自动证明其固有属性数量、神符形态或整件装备的解析已经正确。

| 新稳定 ID（`uniques:`） | 英文名称               | 中文 `name`        | `id` / `key`                                 |
| ----------------------- | ---------------------- | ------------------ | -------------------------------------------- |
| `annihilus`             | Annihilus              | 毁灭               | `2684354` / `S15_Charm_Unique_Annihilus`     |
| `bell_of_the_bovine`    | Bell of the Bovine     | 魔牛之铃           | `2677115` / `OPAL_Amulet_Unique_Generic_100` |
| `leorics_crown`         | Leoric's Crown         | 李奥瑞克的王冠     | `2647147` / `Helm_Unique_Generic_005`        |
| `messerschmidts_reaver` | Messerschmidt's Reaver | 梅塞施密特的劫掠者 | `2647156` / `2HAxe_Unique_Generic_001`       |

后两项另有 2026 年 9 月 13 日暴雪 S15 公告直接佐证：[简中经典暗金段](https://d4.blizzard.cn/news/24295394/index.html)、
[英文同篇经典暗金段](https://news.blizzard.com/en-us/article/24295394/celebrate-30-years-of-diablo-in-season-of-hell-s-legacy)。
本次未找到前两项的官方公告精确对照；它们的证据级别是项目既有支持的同构游戏数据配对，而不是“已在官方公告查到”。

### 两个符印键：名称和描述的证据分开

`C-S-en`/`C-S-zh` 按 `(IdSno,IdName)` 连接后，以下名称可以确认。
“往昔之旅”的来源描述是 `missing description`，不能把该占位文本导入运行目录。

| 新稳定 ID                                    | 中文 `Name`    | 证据身份                                           | 描述范围                     |
| -------------------------------------------- | -------------- | -------------------------------------------------- | ---------------------------- |
| `sigils:dungeons:a_journey_through_the_past` | 往昔之旅       | 下列 9 对 dungeon ID/key 均同名且中英逐项匹配      | 仅确认地下城名称。           |
| `sigils:positive:echo_of_pindleskin`         | 暴躁外皮的回响 | `2683344` / `DungeonAffix_Positive_S15_Pindleskin` | 名称及完整描述均有配对记录。 |

“往昔之旅”的九对身份：

```text
2628613  World_DGN_Jakarta_04
2625722  World_DGN_Jakarta_01
2640409  World_DGN_Jakarta_01_HallsOfDeception
2626494  World_DGN_Jakarta_02
2628123  World_DGN_Jakarta_03
2629350  World_DGN_Jakarta_03_ThroneRoom
2629566  World_DGN_Jakarta_03_WorldStoneChamber
2641818  World_DGN_Jakarta_05_Crawl
2631414  World_DGN_Jakarta_05
```

`echo_of_pindleskin` 的来源中文 `Description` 为：

> 暴躁外皮的回响在这座地下城中游荡，消灭它时可能掉落游戏中的任意物品。

该描述与同身份英文记录逐项对应。正式集成应遵循现有符印目录“名称/描述拼接”的规则，测试真实 TTS 只读名称和含描述两种边界，不能随意修改稳定 ID。

## 一个新词缀与十二个旧贡品仍然缺证据

### `affixes:resistance`：不能把参数化模板截断后的词干当作已确认译名

没有在所核对的 Companion `DescriptionClean` 或 D2Core `desc` 中找到独立英文 `Resistance` 的可靠英/中同身份记录。
d4data 的 `AttributeDescriptions.stl.json` 中 `Resistance` 模板是 `+[{VALUE2}] {VALUE1} Resistance`，其中存在元素参数。
因此，“英文生成结果只剩 resistance”可能涉及参数展开或规范化边界；这是需要追溯生成来源的假设，不是已证明的上游错误。
不能直接从“火焰抗性/冰霜抗性”等文本删去元素名称，自造一个所谓官方译名。

固定来源：[d4data AttributeDescriptions](https://github.com/DiabloTools/d4data/blob/33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0/json/enUS_Text/meta/StringList/AttributeDescriptions.stl.json)。
后续需找到实际生成该 ID 的 affix 身份、对应中文模板或客户端 TTS；之前保持未确认状态。

### 十二个贡品：实机解决一项，其他项目仍无新增对应

这些是先前质量报告中的独立缺口，不包含在本次 16 个新增 ID 的分母里。
原先的 13 项中只有“次级和谐贡品”得到本次实机证明；对余下 12 项核对当前来源和暴雪中文公告没有找到新的精确对应。
这是检索结果，不是断言全网绝不存在。
不能根据已有“强效精炼贡品/巧思贡品”自行扩展前缀。

```text
tributes:greater_tribute_of_armaments
tributes:greater_tribute_of_harmony
tributes:greater_tribute_of_ingenuity
tributes:greater_tribute_of_the_horadrim
tributes:lesser_tribute
tributes:lesser_tribute_of_ingenuity
tributes:lesser_tribute_of_the_horadrim
tributes:major_tribute_of_andariel
tributes:minor_tribute_of_andariel
tributes:tribute_of_andariel
tributes:tribute_of_heritage
tributes:tribute_of_the_horadrim
```

复核入口：[暴雪中文新闻目录](https://d4.blizzard.cn/news/)、[S15 中文公告](https://d4.blizzard.cn/news/24295394/index.html)、
[苏醒赛季中文公告](https://d4.blizzard.cn/news/24268702/index.html)、[憎恨之王说明](https://d4.blizzard.cn/news/24267729/)、
[3.1 中文补丁](https://d4.blizzard.cn/news/24287406/)。

## “恶毒”有两套完整描述，不能合并成同义 ID

`C-P-en` 和 `C-P-zh` 同时保留两条不同身份的记录。此前拒绝歧义名称的策略仍正确；本次补充说明：
已有来源能够支撑后续针对完整描述的保守消歧，但不代表消歧代码已经实现或实机验收。

| 稳定 ID             | `IdSno` / `IdName`                     | 中文 `Name` | 区分机制                                 |
| ------------------- | -------------------------------------- | ----------- | ---------------------------------------- |
| `aspects:malicious` | `2547904` / `legendary_warlock_002_x2` | 恶毒        | 恶魔形态，近距恶魔或敌人带来的伤害提高。 |
| `aspects:virulent`  | `1738556` / `legendary_druid_123`      | 恶毒        | 狂犬撕咬感染，冷却缩短和对感染目标增伤。 |

来源完整中文 `Description` 模板（保留原文标点及 `#`）：

```text
malicious:
处于恶魔形态时，近距范围内每有一名恶魔或敌人，你造成的伤害就会提高 #%，最多提高 #%。

virulent:
狂犬撕咬感染敌人后，其冷却时间缩短 # 秒。当感染对象为精英敌人时，冷却时间缩减变为原来的三倍。此外，你对受到狂犬撕咬影响的敌人额外造成 #% 增伤伤害。
```

英文记录也分别描述这两种机制，并具有相同双字段身份。中文 `virulent` 的“额外造成…增伤伤害”是来源现有措辞，本报告没有润色或重译。
如后续实现，应要求名称候选与完整已知描述一致，允许明确验证过的数值/格式占位变化；名称单独出现、未知描述、混合描述仍应拒绝。
不能仅按一个任意关键词或字符排序猜测 ID。旧补丁的“怨毒之威能”对应另一个英文名称 Aspect of Malevolence，不是这两个记录的更名证据。

## 来源存在不同步：禁止按公告列表位置配对

本次英文 S15 公告的经典暗金列表出现 Sirloin of the Bovine，而中文对应位置仍是斯奎特的罩衫。
因此同一文章编号不意味着两页在检查时刻逐行同步；本报告只采用明确名称或稳定身份一致的配对。
这个差异不能拿来翻译 `bell_of_the_bovine`，也不能单独据此更名已有 `squirts_blouse`。
来源为前述 [简中公告](https://d4.blizzard.cn/news/24295394/index.html) 与 [英文公告](https://news.blizzard.com/en-us/article/24295394/celebrate-30-years-of-diablo-in-season-of-hell-s-legacy)。

## 英文代码审计：一项已等效修复，其他增量尚未移植

`v10.0.3..v10.0.4` 包含两次非合并提交：
`bbe202c8c7a2cf18451666854db464c51fd870ef`（Python 3.14 启动/快捷键）和
`6561068de4464dc3f2040ef659b206a4ae1e2f4c`（S15 数据与 InfinityBuilds）。
[v10.0.4 Release](https://github.com/d4lfteam/d4lf/releases/tag/v10.0.4) 于 2026 年 9 月 18 日 18:55 UTC 发布；检查时 `upstream/main` 与该标签指向同一提交。

| 文件或范围                                       | 上游变化                                                                                          | 相对本地基线的结论与风险                                                                                   |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `src/settings/hotkeys/runtime.py`                | 将 `Callable`/`Hashable` 从仅类型检查导入移到运行时，增加运行时注解检查回归。                     | 本地已经等效修复并保留安全键盘门控；不需要覆盖本地实现。                                                   |
| `src/importing/infinitybuilds/adapter.py`        | 识别 `item-runeword-`，不再把暂不支持的符文之语名写成 `unique_aspect`；保留可识别词缀并给出警告。 | 本地尚未合入；不同于本地 `extraction.py` 的提取边界修复，不能认为后者已覆盖这个问题。                      |
| `src/tools/data_generation/datasets.py`          | 固定通用 Axe/Sword 的英文标签。                                                                   | 本地尚缺；移植时须保留中文别名/已有生成器修复，避免对 zhCN 硬编码英文。                                    |
| `assets/lang/enUS/{affixes,sigils,uniques}.json` | 本报告列出的 10 + 2 + 4 个新增键。                                                                | 无配套 zhCN 更新；15 个候选翻译有证据，但本次未录入。                                                      |
| `uv.lock`、`prek.toml`                           | 11 个依赖更新，包含 filelock 3 → 4 大版本；更新 uv/Ruff 相关钩子。                                | 不应为获得几条数据而盲目更新整个依赖集。若移植，须重新跑全套测试、冻结构建与实机验证，保留已有 PATH 隔离。 |
| 测试与版本标记                                   | 更新版本；删除上游 `tests/init_test.py`，调整架构测试豁免，补充导入/快捷键/生成器测试。           | 本地版本测试仍有用途，不应机械删除或扩大豁免。                                                             |

该 d4lf 增量没有 TTS 解析器、物品过滤、UI、构建开关或 CI 流程逻辑变更；不能把上游版本升级当作解决中文解析缺口的证明。
另一个项目 Companion 的 5 次更新集中在 Mobalytics 的类型转换/链接识别和 InfinityBuilds 的 React Flight 首行、嵌套 children、直接根 `build` 形态；它们是 C# 实现，需要按本项目边界评估，而不是直接复制。
依据：[d4lf 完整差异](https://github.com/d4lfteam/d4lf/compare/v10.0.3...v10.0.4)、[Companion 完整差异](https://github.com/josdemmers/Diablo4Companion/compare/a7efa39819ffec10f2dd1c06e874744d2605167f...5ac10ca801bec9de9f98481584f1a48ecd8e6c6b)。

## 后续集成与验收边界

1. 单独移植 `v10.0.4` 的适用代码和英文目录，不把本报告当作已合并记录。
1. 仅录入上面 15 个已证文本，并在 manifest 记录身份与哈希；`resistance` 和余下 12 个贡品保持缺口可见。
1. 若增加“恶毒”描述消歧，补充两个正例及名称单独/未知/混合描述的拒绝测试，维持失败时不自动标记物品。
1. 回归新神符、项链固有词缀、文本型词缀、符印名称/描述组合；来源配对不能替代实际游戏 TTS 验收。
1. 重新运行来源一致性、目录/解析、全套测试与发布门禁；没有证据前不能将 `runtime_ready` 改成 `true`。

仍需回答：`resistance` 来自哪个实际 affix？余下 12 个贡品何时能得到同身份中文文本？完整“恶毒”模板在当前客户端 TTS 中如何分行？
这些问题会影响集成正确性。本报告不包含新的游戏截图、玩家身份、私人路径或原始个人信息。

## 复核方法与文件证据

检查使用 `git ls-remote`、固定提交的 GitHub compare API，以及 HTTP 读取公开 JSON 后对原始字节计算 SHA-256。
上游核验阶段未切换工作树或覆盖代码/数据；后续获准的限定修改为上文“次级和谐贡品”相关资产、清单和测试，
以及跨平台 JSON 换行、对应生成器与状态文档更正。该核验没有修改上游仓库或发布正式发行版；
报告随本地修复提交，不表示已集成 `v10.0.4`。
下列 18 份来源数据文件均与基线 `assets/catalog/source-lock.json` 匹配；本地译文修复不改变它们的哈希。
表格用于精确身份/哈希查询；没有连续时间序列或适合图表的数值关系，因此不制作趋势图。
报告把技术规范中的范围、方法、限制、建议与开放问题分别放在相关证据旁及本节，交付面仅为指定 Markdown 文件。

### Companion：十份文件均与原锁一致

下面使用本次已验证的新 HEAD 固定链接。它们的字节与原锁 `a7efa39819ffec10f2dd1c06e874744d2605167f` 一致，不要求改写来源锁。

| 代号 / 文件完整来源                                                                                                                                                         | SHA-256                                                            |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| [C-A-en — Affixes.enUS.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Affixes.enUS.json)     | `fdc2db083aa28538c0b63413dc2a9ad9e2c2ad789eff714f9a28cfff7f56fe31` |
| [C-A-zh — Affixes.zhCN.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Affixes.zhCN.json)     | `12fa6467f199221ed6216ccdf9a3b2166ce6677ad3b1dd16db5698c6acefd45b` |
| [C-P-en — Aspects.enUS.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Aspects.enUS.json)     | `4ef5b2e7aa4f8285bc0566e67dcb381886429dc5405ae1f82eb62bd077d40c1c` |
| [C-P-zh — Aspects.zhCN.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Aspects.zhCN.json)     | `9d1001aac46e3011356d54f69a4c2d8071baa0bdfc919d8a36fabf8aa1b34b44` |
| [C-T-en — ItemTypes.enUS.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/ItemTypes.enUS.json) | `df3a042c7764eb433751bb20f18d4fb6b3057c2db9d507b1dc7c62a5759eb6f6` |
| [C-T-zh — ItemTypes.zhCN.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/ItemTypes.zhCN.json) | `aa21f3358105d6e0004018b469c6f74108e30292e76298061f2f51d3d7bee861` |
| [C-S-en — Sigils.enUS.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Sigils.enUS.json)       | `9debf035eba46b2dc95fda8076b04a58d771458197370bef4ceadcc942db13cb` |
| [C-S-zh — Sigils.zhCN.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Sigils.zhCN.json)       | `c318c227ae34c3fcdbe8ebde21d56024136a9c325f3d33c009120794c5c0c60e` |
| [C-U-en — Uniques.enUS.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Uniques.enUS.json)     | `04c5777f2ea5f320018fe1aeec2cc427ffdabbb1daa09accbfb46c857b5631fd` |
| [C-U-zh — Uniques.zhCN.json](https://raw.githubusercontent.com/josdemmers/Diablo4Companion/5ac10ca801bec9de9f98481584f1a48ecd8e6c6b/D4Companion/Data/Uniques.zhCN.json)     | `4649122ccb80166d6ca45c630973e06db2b8627536cd989e8004e52ef2ef0b56` |

### D2Core：八份文件均与原锁一致

公开数据 URL 的 `env=prod&v=8` 为固定公开请求参数，不是账号凭据。对可变 HTTP 资源应始终同时核对下列内容哈希。

| 代号 / 文件完整来源                                                                                              | SHA-256                                                            |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| [D-A-en — affix_enUS.json](https://cloudstorage.d2core.com/data/d4/73552/affix_enUS.json?env=prod&v=8)           | `97a02211dda70118f3e0876e603e6538eec395e4764422f4bd4a9fbce3d3af96` |
| [D-A-zh — affix_zhCN.json](https://cloudstorage.d2core.com/data/d4/73552/affix_zhCN.json?env=prod&v=8)           | `d4f8325f16a17258007a797072c518d0c82e9b610981dd1ea83ec969b9eb9d1e` |
| [D-P-en — aspect_enUS.json](https://cloudstorage.d2core.com/data/d4/73552/aspect_enUS.json?env=prod&v=8)         | `39af68d6c7d85c5ccd783652dbfb40beee1ffcabaa32ad88c782c65e418203f1` |
| [D-P-zh — aspect_zhCN.json](https://cloudstorage.d2core.com/data/d4/73552/aspect_zhCN.json?env=prod&v=8)         | `e6704fb2512ff85332c422911fabe0a2c5ea7ca203eb5dcd2b18110d9f617d33` |
| [D-C-en — talisman_enUS.json](https://cloudstorage.d2core.com/data/d4/73552/talisman_enUS.json?env=prod&v=8)     | `2279ffcd1a93d978beba3c7d7be9ecdbd0f62e0654c7492eec718c429de355ff` |
| [D-C-zh — talisman_zhCN.json](https://cloudstorage.d2core.com/data/d4/73552/talisman_zhCN.json?env=prod&v=8)     | `5f13c6ad41ebe6b4a2224ddca74caca1130b6c0a6a3d353ab2bbc53779ac9449` |
| [D-U-en — uniqueItem_enUS.json](https://cloudstorage.d2core.com/data/d4/73552/uniqueItem_enUS.json?env=prod&v=8) | `f6f92e7444df3cc32d06f685ddc9f15443458b33f90ca1a5c1c62ec93fe50c64` |
| [D-U-zh — uniqueItem_zhCN.json](https://cloudstorage.d2core.com/data/d4/73552/uniqueItem_zhCN.json?env=prod&v=8) | `c482b1aea7c241aeeca55c831f2cd6dd9c57d0fb4c5a2f4261f20793ba01f964` |
