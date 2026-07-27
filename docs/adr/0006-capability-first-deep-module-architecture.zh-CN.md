# 能力优先的深模块架构

[English](0006-capability-first-deep-module-architecture.md)

D4LF 正从按技术层划分的包重构为能力优先的深模块。每项能力拥有自己的行为，并通过
`__init__.py` 暴露刻意收窄的包门面。其他能力的调用方只能导入该门面。最终布局使用描述性、
无前缀的实现名称；私有性由包所有权和门面导入规则保证，而不是依赖前导下划线。

## 决策

目标源码布局包含以下能力包：

| 能力        | 包门面           | 外部契约                                                       |
| ----------- | ---------------- | -------------------------------------------------------------- |
| Item        | `src.item`       | 物品值、规则以及保留/丢弃评估                                  |
| Profiles    | `src.profiles`   | Profile 文档，以及 `ProfileSession` 加载、保存、验证和结果类型 |
| Settings    | `src.settings`   | 类型化设置、持久化、重载决策、坐标和热键绑定                   |
| Importing   | `src.importing`  | 规范化导入请求与结果、来源选择和文件名组装                     |
| Perception  | `src.perception` | 物品文本获取与解析、截图、说明框定位和图像诊断                 |
| Paragon     | `src.paragon`    | 巅峰盘载荷转换、选择和悬浮层控制                               |
| Automation  | `src.automation` | 游戏窗口、热键、指针移动以及物品栏、储物箱和商人操作           |
| Loot        | `src.loot`       | 通过能力接口管理过滤模式生命周期和编排                         |
| Overlay     | `src.overlay`    | 会话统计、首领悬浮层生命周期、更新和定位                       |
| Desktop     | `src.desktop`    | 共享 Qt/Tk 基础组件、对话框、主题、活动日志和 UI 线程分发      |
| Application | `src.app`        | 组合、启动、日志、更新检查和关闭                               |
| Tools       | `src.tools`      | 回放和数据生成入口                                             |

`src.main` 仍是可执行入口，不是通用公共 API。每项能力可以包含内聚的公共子包，每个包或
子包都从 `__init__.py` 暴露明确接口。子包内部可以使用实现模块，但调用方不能直接导入实现
路径。除非某个子包被明确记录为跨能力边界，否则能力根门面是唯一的跨能力导入位置。应用
组合层负责在运行时连接多个能力门面；跨能力集成测试可组合这些公共门面。该规则适用于生产
代码、包接口测试、测试 patch、构建配置和动态 Windows 导入。聚焦的单元测试只能导入被测
能力自身的实现模块。

Profile 编辑器按公共子包组织，而不是放进技术型 GUI 容器：

| 子包                      | 职责                                                      | 公共接口                           |
| ------------------------- | --------------------------------------------------------- | ---------------------------------- |
| `src.profiles.affix`      | 词缀池、物品类型/稀有度/强度/强力词缀控件及可复用词缀组件 | `src.profiles.affix.__init__`      |
| `src.profiles.aspect`     | 威能升级和暗金特效编辑                                    | `src.profiles.aspect.__init__`     |
| `src.profiles.unique`     | 全局暗金编辑                                              | `src.profiles.unique.__init__`     |
| `src.profiles.charm_seal` | 共享典籍与淬炼手册编辑、对话框和标签页                    | `src.profiles.charm_seal.__init__` |
| `src.profiles.sigil`      | 梦魇地下城钥匙标签页、组件和对话框                        | `src.profiles.sigil.__init__`      |
| `src.profiles.tribute`    | 贡品标签页和对话框                                        | `src.profiles.tribute.__init__`    |
| `src.profiles.editor`     | 共享 Profile 编辑器基础组件与组合                         | `src.profiles.editor.__init__`     |

这些子包门面在 Profiles 能力内部公开，但不会让 Qt 控件进入顶层 `src.profiles` 跨能力契约。

能力根门面导出行为和领域结果类型，不导出实现类、GUI 控件或通用服务定位器。能力自身的 UI
子包门面可以向该能力内部调用方导出控件、对话框和编辑器组合类型，但这些类型不会成为能力根
的跨能力契约。只有第二项能力出现具体需求时，门面才增加新操作。能力专属 GUI 归对应能力所有；
`src.desktop` 只保留确实有多个使用方的基础组件。

Desktop 中明确记录的 UI 子包边界，是多个能力共享可复用表现层组件时的例外：

| 子包                   | 职责                                  | 公共接口                                      |
| ---------------------- | ------------------------------------- | --------------------------------------------- |
| `src.desktop.widgets`  | 可复用 Qt 控件和应用强调色配置        | `CheckmarkCheckBox`, `set_accent_color`       |
| `src.desktop.activity` | ANSI 日志展示和线程安全的 Qt 日志投递 | `ANSIConsoleWidget`, `QtLogHandler`           |
| `src.desktop.themes`   | 共享深色/浅色 Qt 样式表模板           | `DARK_THEME_TEMPLATE`, `LIGHT_THEME_TEMPLATE` |

这些子包是明确的跨能力边界；其实现模块仍保持私有。

## 修正后的最终布局（结构审查，2026-07-19）

下方迁移清单记录历史源码路径，但冻结目标是以下包结构。每个列出的包（包括嵌套包）都在
`__init__.py` 中拥有其公共接口；实现文件使用普通描述性名称，不使用前导下划线。

| 区域        | 最终包边界                                                                                                                                                           |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Application | `src.app.dashboard` 拥有仪表板控件、拖动和 Profile 组合；`src.app` 保留外壳和生命周期组合                                                                            |
| Automation  | `src.automation.window` 拥有窗口契约以及真实 Windows/no-op 适配器                                                                                                    |
| Overlay     | `src.overlay.widget` 拥有控件行为；生命周期、统计和跟踪保留为同级边界                                                                                                |
| Paragon     | `src.paragon.overlay` 拥有悬浮层行为；转换和数据保留在 `src.paragon`                                                                                                 |
| Perception  | `src.perception.backend`、`.matching`、`.capture`、`.parser` 和 `.tooltip` 是带门面的公共子包                                                                        |
| Profiles    | `src.profiles.affix.group` 拥有词缀组行为；`src.profiles.editor.dialogs` 和 `.profile` 拥有编辑器对话框/Profile 组合；`src.profiles.validation` 将验证集中到内聚模块 |
| Settings    | `src.settings.models` 是公共模型边界；模型实现在该包下                                                                                                               |
| Desktop     | `src.desktop.activity`、`.themes` 和 `.widgets` 是承载实现的子包，并各自从 `__init__.py` 暴露接口                                                                    |
| Importing   | `src.importing.paragon` 包含一个规范化巅峰盘处理公共模块；各来源的提取逻辑保留在 `d4builds`、`infinitybuilds`、`maxroll` 和 `mobalytics` 包中                        |

镜像单元测试树严格遵循包和模块结构：包初始化文件对应 `init_test.py`，每个实现模块对应
`<module>_test.py`。同一能力的测试可以导入其实现模块；跨能力测试只使用已记录的门面。

## 高风险边界选择

| 边界       | 拒绝的设计                                                                 | 采用的设计                                                                                   | 原因                                                            |
| ---------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Importing  | 来源适配器返回各自数据，由调用方协调重试、浏览器、Profile 转换和巅峰盘导出 | `ImportSource` 接受规范请求，返回包含所选变体、Profile 输出和可选巅峰盘载荷的统一结果        | 把来源提取限制在适配器内，并保持单一完整导入流程                |
| Perception | 一个带模式开关的可变感知服务，同时处理 TTS、截图、模板、几何和解析         | 小型查询式门面返回带类型的物品文本、说明框位置和图像诊断结果；Windows/no-op 后端是真实适配器 | 保留诊断能力，同时分开独立的获取和解释行为                      |
| Overlay    | 调用方直接访问全局 Tk 悬浮层并协调创建、渲染、更新和关闭                   | 生命周期端口公开创建、更新、可见性、定位和关闭，渲染保持私有                                 | 保留线程和 Windows 限制，让应用与 Loot 调用方不依赖 Tk 内部实现 |
| Desktop    | 把所有能力窗口集中到通用 GUI 工具包                                        | 能力 UI 归能力自身，只通过能力门面提供共享桌面基础组件和应用外壳组合                         | 避免 Desktop 再次变成宽泛技术容器，并让表现知识归行为所有者     |

所选边界是围绕已观察变化建立的窄而带类型的端口。它们不允许推测性接口、兼容转发模块或
注册表/服务定位器层。

## 源码迁移清单

`P` 表示未来的包门面，`X` 表示由该门面重新导出的窄而明确的边界，`I` 表示实现模块，
`E` 表示可执行入口。实现模块由包所有，不依赖名称改写。`Keep` 表示在最终能力中保留内聚
模块，`Move` 表示完整移动，`Split` 表示在移动前或过程中按内聚行为拆分，`Delete` 表示
删除前必须检查全仓库、PyInstaller、动态导入和 Windows 可达性。

| 当前模块                                           | 能力所有者  | 角色 | 处置   |
| -------------------------------------------------- | ----------- | ---- | ------ |
| `src/__init__.py`                                  | Application | P    | Keep   |
| `src/autoupdater.py`                               | Application | I    | Keep   |
| `src/cam.py`                                       | Perception  | I    | Move   |
| `src/config/__init__.py`                           | Settings    | P    | Move   |
| `src/config/data.py`                               | Perception  | I    | Split  |
| `src/config/helper.py`                             | Settings    | I    | Split  |
| `src/config/loader.py`                             | Settings    | I    | Split  |
| `src/config/profile_document.py`                   | Profiles    | I    | Keep   |
| `src/config/profile_models.py`                     | Profiles    | I    | Split  |
| `src/config/profile_session.py`                    | Profiles    | X    | Keep   |
| `src/config/reload_groups.py`                      | Settings    | I    | Keep   |
| `src/config/settings_models.py`                    | Settings    | I    | Split  |
| `src/config/ui.py`                                 | Perception  | I    | Split  |
| `src/dataloader.py`                                | Item        | I    | Move   |
| `src/gui/__init__.py`                              | Desktop     | P    | Move   |
| `src/gui/importer_window.py`                       | Importing   | I    | Split  |
| `src/gui/importer/__init__.py`                     | Importing   | P    | Move   |
| `src/gui/importer/d4builds.py`                     | Importing   | I    | Split  |
| `src/gui/importer/gui_common.py`                   | Importing   | I    | Split  |
| `src/gui/importer/import_pipeline.py`              | Importing   | X    | Split  |
| `src/gui/importer/importer_config.py`              | Importing   | X    | Keep   |
| `src/gui/importer/infinitybuilds.py`               | Importing   | I    | Split  |
| `src/gui/importer/maxroll.py`                      | Importing   | I    | Split  |
| `src/gui/importer/mobalytics.py`                   | Importing   | I    | Split  |
| `src/gui/importer/paragon_export.py`               | Importing   | I    | Move   |
| `src/gui/models/__init__.py`                       | Desktop     | P    | Move   |
| `src/gui/models/activity_log_widget.py`            | Desktop     | I    | Split  |
| `src/gui/models/checkmark_checkbox.py`             | Desktop     | I    | Move   |
| `src/gui/models/collapsible_widget.py`             | Profiles    | I    | Move   |
| `src/gui/models/dialog.py`                         | Desktop     | I    | Split  |
| `src/gui/models/open_user_config_button.py`        | Desktop     | I    | Delete |
| `src/gui/models/rule_list_tab.py`                  | Profiles    | I    | Move   |
| `src/gui/models/tab_group_widget.py`               | Profiles    | I    | Move   |
| `src/gui/open_user_config_button.py`               | Desktop     | I    | Delete |
| `src/gui/profile_editor_window.py`                 | Profiles    | I    | Move   |
| `src/gui/profile_editor/__init__.py`               | Profiles    | P    | Move   |
| `src/gui/profile_editor/affixes_tab.py`            | Profiles    | I    | Split  |
| `src/gui/profile_editor/aspect_upgrades_tab.py`    | Profiles    | I    | Move   |
| `src/gui/profile_editor/charms_seals_group_tab.py` | Profiles    | I    | Split  |
| `src/gui/profile_editor/global_uniques_tab.py`     | Profiles    | I    | Move   |
| `src/gui/profile_editor/profile_editor.py`         | Profiles    | I    | Move   |
| `src/gui/profile_editor/sigils_tab.py`             | Profiles    | I    | Split  |
| `src/gui/profile_editor/tributes_tab.py`           | Profiles    | I    | Move   |
| `src/gui/profile_tab.py`                           | Profiles    | I    | Split  |
| `src/gui/settings_store.py`                        | Settings    | I    | Move   |
| `src/gui/settings_tab.py`                          | Settings    | I    | Split  |
| `src/gui/settings_window.py`                       | Settings    | I    | Move   |
| `src/gui/themes.py`                                | Desktop     | I    | Split  |
| `src/gui/unified_window.py`                        | Application | I    | Split  |
| `src/item/__init__.py`                             | Item        | P    | Keep   |
| `src/item/data/__init__.py`                        | Item        | P    | Keep   |
| `src/item/data/affix.py`                           | Item        | I    | Keep   |
| `src/item/data/aspect.py`                          | Item        | I    | Keep   |
| `src/item/data/item_type.py`                       | Item        | I    | Keep   |
| `src/item/data/rarity.py`                          | Item        | I    | Keep   |
| `src/item/data/seasonal_attribute.py`              | Item        | I    | Keep   |
| `src/item/descr/__init__.py`                       | Perception  | P    | Move   |
| `src/item/descr/geometry_locator.py`               | Perception  | I    | Split  |
| `src/item/descr/read_descr_tts.py`                 | Perception  | I    | Split  |
| `src/item/descr/text.py`                           | Perception  | I    | Move   |
| `src/item/descr/texture.py`                        | Perception  | I    | Move   |
| `src/item/filter.py`                               | Item        | I    | Split  |
| `src/item/find_descr.py`                           | Perception  | I    | Move   |
| `src/item/models.py`                               | Item        | I    | Keep   |
| `src/item/sigil_rules.py`                          | Item        | X    | Keep   |
| `src/logger.py`                                    | Application | I    | Keep   |
| `src/loot_mover.py`                                | Automation  | I    | Move   |
| `src/main.py`                                      | Application | E    | Keep   |
| `src/overlay.py`                                   | Overlay     | X    | Move   |
| `src/paragon_overlay.py`                           | Paragon     | I    | Split  |
| `src/paragon_transform.py`                         | Paragon     | I    | Keep   |
| `src/scripts/__init__.py`                          | Loot        | P    | Move   |
| `src/scripts/common.py`                            | Loot        | I    | Split  |
| `src/scripts/handler.py`                           | Application | X    | Split  |
| `src/scripts/info_overlay.py`                      | Overlay     | I    | Split  |
| `src/scripts/loot_filter_tts.py`                   | Loot        | I    | Move   |
| `src/scripts/vision_mode_fast.py`                  | Loot        | I    | Move   |
| `src/scripts/vision_mode_with_highlighting.py`     | Loot        | I    | Split  |
| `src/startup_messages.py`                          | Application | I    | Keep   |
| `src/template_finder.py`                           | Perception  | I    | Split  |
| `src/tools/__init__.py`                            | Tools       | P    | Keep   |
| `src/tools/gen_data_helpers.py`                    | Tools       | I    | Keep   |
| `src/tools/gen_data.py`                            | Tools       | I    | Split  |
| `src/tools/replay_common.py`                       | Tools       | I    | Keep   |
| `src/tools/replay_cropped_tooltip.py`              | Tools       | I    | Split  |
| `src/tools/replay_full_screenshot.py`              | Tools       | I    | Move   |
| `src/tools/replay_template_matching.py`            | Tools       | I    | Move   |
| `src/tts_backend_noop.py`                          | Perception  | I    | Move   |
| `src/tts_backend_windows.py`                       | Perception  | I    | Move   |
| `src/tts.py`                                       | Perception  | X    | Split  |
| `src/ui_thread.py`                                 | Desktop     | I    | Move   |
| `src/ui/__init__.py`                               | Automation  | P    | Move   |
| `src/ui/char_inventory.py`                         | Automation  | I    | Move   |
| `src/ui/inventory_base.py`                         | Automation  | I    | Move   |
| `src/ui/menu.py`                                   | Automation  | I    | Move   |
| `src/ui/stash.py`                                  | Automation  | I    | Move   |
| `src/ui/vendor.py`                                 | Automation  | I    | Move   |
| `src/utils/__init__.py`                            | Automation  | P    | Move   |
| `src/utils/custom_mouse.py`                        | Automation  | I    | Move   |
| `src/utils/hotkeys.py`                             | Automation  | I    | Move   |
| `src/utils/image_operations.py`                    | Perception  | I    | Move   |
| `src/utils/misc.py`                                | Perception  | I    | Split  |
| `src/utils/process_handler.py`                     | Automation  | I    | Move   |
| `src/utils/roi_operations.py`                      | Perception  | I    | Move   |
| `src/utils/window_backend_noop.py`                 | Automation  | I    | Move   |
| `src/utils/window_backend_windows.py`              | Automation  | I    | Move   |
| `src/utils/window_backend.py`                      | Automation  | X    | Move   |
| `src/utils/window.py`                              | Automation  | X    | Split  |

## 基线与门禁

在此决策点，架构锁定提交 `3fbac7b` 的 `src` 下有 108 个 Python 模块和 26,229 行物理代码。
规划记录的 26,213 行少算了 16 行；26,229 是可复现的历史源码基线，也是此次重构允许的
生产源码最大行数。架构冻结前，任何增加都需要记录抵扣。当前 300 行门禁报告 29 个源码和
8 个测试违规；这些是计划中的迁移工作，不是豁免。

macOS 行为基线是 586 个非 Selenium 测试通过、47 个跳过。源码模块移动期间保留现有测试，
测试树镜像推迟到源码架构冻结后。

行数门禁检查 `src` 与 `tests` 下每个 Python 文件不超过 300 物理行。它属于
`uv run prek run -a`，也可在聚焦源码切片中运行：

```bash
uv run --no-project hooks/check_lines.py
```

门禁配置和 Hook 实现是记录决策时已经存在的用户改动。本 ADR 只记录其契约，不声明拥有或替换它们。

## 影响

- 重构切片按依赖顺序移动，并把所有仓库导入、patch 目标、构建引用和动态 Windows 导入更新到最终包路径；不保留旧路径兼容模块。
- 在结构移动前明确所有能力边界，使后续工单能按清单验证归属，而不是创建新的技术容器。
- 只有全部源码通过行数门禁、源码行数不超过 26,229 历史基线（或已批准并记录抵扣），且完整非 Selenium 行为测试通过后，源码架构才能冻结。
- 两个标记为删除的模块在完成非 Python、动态、Windows 和 PyInstaller 可达性验证前仍保留在源码中。

## 源码冻结审计

2026-07-18 的源码迁移审计完成了无需等待测试树镜像的结构检查：

- 最后一个超长源码模块（导入器巅峰盘导出）已拆分到内聚的 `src.importing.paragon` 公共模块后。来源专属提取保留在各来源包，通用巅峰盘转换和悬浮层行为仍归 `src.paragon`。
- 数据加载归 `src.item.data.loader` 并从 `src.item` 暴露；文本名称规范化归 `src.perception`；运行时协调器归 `src.app`；悬浮层单例状态归 `src.overlay`。
- 全仓库导入与入口搜索完成后，删除了过时的 `src.dataloader`、`src.scripts`、`src.utils` 和空的平行 GUI 包。跨能力生产与测试调用方现在使用能力门面或已记录子包门面。
- `src` 下每个 Python 文件都不超过 300 物理行。完整非 Selenium 测试为 688 个通过、16 个跳过，`ty` 通过。

历史 26,229 行预算尚未达到：审计后的源码树为 27,185 行，比修正基线多 956 行。新增行分布
在迁移引入的能力实现和门面中；仓库引用审计、Ruff 和 Vulture 都没有发现无用或兼容源码。
这是仍需批准的明确预算协调决策，不是隐含豁免。

全仓库 `check_lines` Hook 仍报告由测试镜像工单负责的 7 个既有超长测试文件。其他 prek
Hook 均通过，完整非 Selenium 测试仍为 688 个通过、16 个跳过。因此本次审计不宣告源码
结构冻结；源码预算决策和测试树门禁继续作为明确的后续工作。

## 源码预算协调

2026-07-19，项目所有者批准了 956 行生产源码抵扣。接受的源码预算因此为 27,185 物理行：
修正后的 26,229 行架构锁定基线加上获批抵扣。测试单独统计，不能解释该抵扣；同期测试从
10,925 行降至 10,896 行。
