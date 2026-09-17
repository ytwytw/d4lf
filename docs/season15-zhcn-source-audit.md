# 第 15 赛季简中数据审计

本文件记录 d4lf `v10.0.3` 第 15 赛季英文增量的简体中文来源。目标是让更新可复核，并避免把机器翻译或推测写入运行时数据。

## 上游范围

- d4lf 上游标签：`v10.0.3`
- d4lf 上游提交：`3ecfe3b904b67d5119830668867626ec678fc7ad`
- d4data 构建：`3.2.1.73552`
- d4data 提交：`33e0bfbb5f717d3e560d14a7fb27d5a7f17fd2c0`
- Diablo4Companion 提交：`a7efa39819ffec10f2dd1c06e874744d2605167f`
- D2Core 配对数据构建：`73552`

`v10.0.3` 相对中文分支原基线只增加 1 个装备词缀与 7 个暗金稳定 ID。暴雪国服的第 15 赛季文章列出了九件经典暗金，但 d4lf 上游数据只增加下表中的七件；未出现在上游目录中的“李奥瑞克的王冠”和“梅塞施密特的劫掠者”没有被擅自创建稳定 ID。

## 已采用翻译

| 稳定 ID | 英文 | 简体中文 | 依据 |
| --- | --- | --- | --- |
| `affixes:gold_drop_rate` | Gold Drop Rate | 金币掉落几率 | 构建 73552 的 D2Core 英/简中同 ID 配对记录；该文本也已存在于本项目同名护身符词缀中 |
| `uniques:ariocs_needle` | Arioc's Needle | 艾里欧克之针 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |
| `uniques:henris_perquisition` | Henri's Perquisition | 亨利的永恒追捕 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |
| `uniques:in-geom` | In-geom | 寅剑 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |
| `uniques:nemesis_bracers` | Nemesis Bracers | 复仇者护腕 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |
| `uniques:squirts_blouse` | Squirt's Blouse | 斯奎特的罩衫 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |
| `uniques:stone_of_jordan` | Stone of Jordan | 乔丹之石 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |
| `uniques:the_furnace` | The Furnace | 焚炉 | 暴雪国服第 15 赛季文章及构建 73552 配对记录 |

暴雪简中原文：<https://d4.blizzard.cn/news/24295394/>。文章中的“经典暗金”与 `3.2.1` 补丁说明分别重复列出了上述七件装备，可相互核对。

## 数据完整性

D2Core 快照只使用公开静态 JSON，并要求同一构建内的英/简中记录按 `(key, id)` 成对匹配：词缀各 1057 条、威能各 363 条、暗金各 380 条、护身符展开记录各 836 条。每个锁定文件的 URL 与 SHA-256 均记录在 `assets/catalog/source-lock.json`。

若后续英文上游出现新稳定 ID，但暴雪简中页面和同构游戏数据均无法给出可信翻译，应保留为空并阻止发布，不得根据英文自行翻译。
