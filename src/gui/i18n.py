from __future__ import annotations

import re
from string import Formatter
from typing import TYPE_CHECKING, override

from PyQt6.QtCore import QEvent, QObject, QSignalBlocker
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QTabWidget,
    QWidget,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

EN_US = "enUS"
ZH_CN = "zhCN"

_ZH_CN_TEXT = {
    # Main window and dashboard
    "D4LF - Diablo 4 Loot Filter v{version}": "D4LF - 暗黑破坏神 IV 装备过滤器 v{version}",
    "Dashboard": "控制台",
    "Full Logs": "完整日志",
    "Diagnostics": "诊断采集",
    "Vision Mode: RUNNING": "视觉模式：运行中",
    "Vision Mode: STOPPED": "视觉模式：已停止",
    "TTS: Connected": "TTS：已连接",
    "TTS: Disconnected": "TTS：未连接",
    "ACTIVE PROFILES": "已启用的配置方案",
    "Toggle profiles to enable them. Drag <b>⠿</b> to set priority; the top profile determines affix highlighting.": "切换配置方案以启用或停用。拖动 <b>⠿</b> 调整优先级；最上方方案决定词缀高亮。",
    "Filter profiles...": "筛选配置方案...",
    "Enable All": "全部启用",
    "Disable All": "全部停用",
    "KEYBOARD SHORTCUTS": "键盘快捷键",
    "Show Activity Log": "显示活动日志",
    "Import Profile": "导入配置方案",
    "Settings": "设置",
    "Minimize to Tray": "最小化到托盘",
    "Restore": "恢复窗口",
    "Exit": "退出",
    "D4 Loot Filter": "暗黑破坏神 IV 装备过滤器",
    "No Profiles found. Please import a profile below.": "未找到配置方案，请先导入。",
    "Edit": "编辑",
    "Edit Profile": "编辑配置方案",
    "Delete": "删除",
    "Delete Profile": "删除配置方案",
    "Are you sure you want to permanently delete the profile '{name}'?": "确定要永久删除配置方案“{name}”吗？",
    "Last Modified: {time}": "最后修改：{time}",
    "Items: {items}": "物品：{items}",
    "Affix Filters: {count}": "词缀过滤器：{count}",
    "Aspect Upgrades: {count}": "威能升级：{count}",
    "Global Uniques: {count}": "全局暗金：{count}",
    "Sigils: Included": "符印：已包含",
    "Tributes: Included": "贡品：已包含",
    "Paragon Overlay: Data Found": "巅峰面板：已找到数据",
    "Path: {path}\n(Could not parse profile details)": "路径：{path}\n（无法解析配置方案详情）",
    # Diagnostics
    "Capture: Idle": "采集：空闲",
    "Capture: Recording ({elapsed})": "采集：录制中（{elapsed}）",
    "Capture: Error": "采集：错误",
    "Capture: Saved": "采集：已保存",
    "Capture: Saved, replay unavailable": "采集：已保存，无法回放",
    "Capture: Saved - {frames} item frames": "采集：已保存，识别出 {frames} 件物品",
    "{count} messages": "{count} 条消息",
    # Loot overlay
    "Unknown item": "未知物品",
    "Mythic (Always Kept)": "神话暗金（始终保留）",
    "Mythics always kept": "神话暗金始终保留",
    "Codex Upgrade": "力量法典升级",
    "Sanctified (Not Supported)": "圣化物品（暂不支持）",
    "{profile} (incl. Set)": "{profile}（含套装）",
    "AspectUpgrades": "威能升级",
    "Cosmetics": "外观物品",
    "Sigils not filtered": "未过滤符印",
    "Mythic Sigil": "神话符印",
    "Mythic Seal": "神话印记",
    "Mythic Charm": "神话护身符",
    "Tributes not filtered": "未过滤贡品",
    "Mythic Tribute": "神话贡品",
    # Info overlay
    "D4LF Boss Timer": "D4LF 信息浮层",
    "World Boss:": "世界首领：",
    "Legion:": "军团：",
    "Helltide:": "地狱狂潮：",
    "GPH:": "金币/小时：",
    "Gained:": "获得金币：",
    "|Gained:": "|获得金币：",
    "EPH:": "经验/小时：",
    "Exp:": "获得经验：",
    "|Exp:": "|获得经验：",
    "T2L:": "升级倒计时：",
    "Next Scan:": "下次扫描：",
    "|Next Scan:": "|下次扫描：",
    "Pending": "等待采集",
    "Ready": "就绪",
    "ACTIVE": "进行中",
    "Off": "关闭",
    "Never": "从不",
    "SETTINGS": "浮层设置",
    "World Boss": "世界首领",
    "Legion": "军团",
    "Helltide": "地狱狂潮",
    "Track Gold": "记录金币",
    "Show Gold Per Hour": "显示每小时金币",
    "Show Gold Gained": "显示获得金币",
    "Gold Config": "金币设置",
    "Track Exp": "记录经验",
    "Show EXP Per Hour": "显示每小时经验",
    "Show EXP Gained": "显示获得经验",
    "Show Time to Level": "显示升级时间",
    "Show Next Scan": "显示下次扫描",
    "Auto-Capture Exp When Inventory Opened": "打开背包时自动采集经验",
    "EXP Capture Time": "经验采集间隔",
    "Configure EXP Bar Position": "设置经验条位置",
    "Reset EXP Bar Position": "重置经验条位置",
    "Exp Config": "经验设置",
    "Reset Gold": "重置金币统计",
    "Reset Exp": "重置经验统计",
    "Reset Stats": "重置统计",
    "Orientation: {orientation}": "布局：{orientation}",
    "Horizontal": "横向",
    "Vertical": "纵向",
    "Increase Size (+)": "增大字号（+）",
    "Decrease Size (-)": "减小字号（-）",
    "Font": "字体",
    "Refresh Timers Now": "立即刷新计时器",
    "Lock Position": "锁定位置",
    "Close Overlay": "关闭浮层",
    "DRAG ACROSS YOUR EXPERIENCE BAR\n(Escape to cancel)": "横跨经验条拖动\n（按 Esc 取消）",
    # Paragon overlay
    "D4LF Paragon Overlay": "D4LF 巅峰浮层",
    "Paragon": "巅峰盘",
    "Compact View": "紧凑视图",
    "Full View": "完整视图",
    "Settings⚙ ▼": "设置⚙ ▼",
    "Builds ▼": "构筑 ▼",
    "Unknown Build": "未知构筑",
    "Ungrouped": "未分组",
    "Step {number}": "阶段 {number}",
    "No Glyph": "无雕文",
    "Grid locked": "网格已锁定",
    "Grid unlocked": "网格未锁定",
    "Golden frames": "金色边框",
    "Golden frames (on)": "金色边框（开）",
    "Golden frames (off)": "金色边框（关）",
    "Reload profiles": "重新加载配置方案",
    "Reset grid defaults": "恢复网格默认设置",
    "Grid Zoom": "网格缩放",
    "Move\nGrid": "移动\n网格",
    (
        "• Drag frame to move grid\n"
        "• D-Pad ↑ ↓ ← → moves grid per click\n"
        "• Use − + buttons to zoom\n"
        "• Use ★ to make all frames golden\n"
        "• Use ↺ to reset to default size/position\n"
        "• Use 🔓 to unlock/lock grid"
    ): (
        "• 拖动边框移动网格\n"
        "• 点击方向键 ↑ ↓ ← → 微调网格\n"
        "• 使用 − + 按钮缩放\n"
        "• 使用 ★ 将所有边框设为金色\n"
        "• 使用 ↺ 恢复默认大小和位置\n"
        "• 使用 🔓 解锁或锁定网格"
    ),
    # Paragon classes; board/glyph proper names live in src.paragon_names.
    "Barbarian": "野蛮人",
    "Druid": "德鲁伊",
    "Necromancer": "死灵法师",
    "Rogue": "游侠",
    "Sorcerer": "巫师",
    "Spiritborn": "灵巫",
    "Paladin": "圣骑士",
    "Warlock": "术士",
    "Locale": "语言",
    "Game build": "游戏版本",
    "Capture category": "采集类别",
    "Game area": "游戏区域",
    "Core equipment": "核心装备",
    "Talisman equipment": "护符装备",
    "Sigils and tributes": "符印与贡品",
    "Custom": "自定义",
    "Inventory": "背包",
    "Equipped": "已装备",
    "Vendor": "商人",
    "Stash": "储藏箱",
    "Mixed equipment": "混合装备界面",
    "Start Capture": "开始采集",
    "Stop and Save": "结束并保存",
    "Open Folder": "打开文件夹",
    "Raw capture": "原始采集",
    "Replay report": "回放报告",
    "Detect build from the running Diablo IV process": "从正在运行的暗黑破坏神 IV 进程检测版本",
    "Invalid game build": "游戏版本无效",
    "Enter the exact four-part Diablo IV game build.": "请输入完整的四段式暗黑破坏神 IV 游戏版本。",
    "Capture failed": "采集失败",
    "Game build not detected": "未检测到游戏版本",
    "Start Diablo IV, then try again, or enter the exact four-part build manually.": "请先启动暗黑破坏神 IV 后重试，或手动输入完整的四段式版本。",
    # Settings shell
    "Search settings...": "搜索设置...",
    "Key Bindings": "快捷键",
    "Technical Settings": "技术设置",
    "Reset to defaults": "恢复默认值",
    "Restart required": "需要重启",
    "Vision mode changes require restarting d4lf. Restart now?": "更改视觉模式需要重启 D4LF。现在重启吗？",
    "Restart now": "立即重启",
    "Later": "稍后",
    "Restart failed": "重启失败",
    "d4lf could not be restarted automatically. Please restart it manually.": "D4LF 无法自动重启，请手动重启。",
    "Error validating value": "设置值验证失败",
    "There was an error setting {key} to {value}. See error below.\n\n": "无法将设置 {key} 更改为 {value}，错误如下：\n\n",
    "Your value has been reset to its previous version.\n\n": "该值已恢复为先前版本。\n\n",
    "Reset Settings": "重置设置",
    "Would you like to reset only the '{tab_name}' settings or all settings to defaults?": "要仅重置“{tab_name}”中的设置，还是将所有设置恢复为默认值？",
    "Reset {tab_name}": "重置 {tab_name}",
    "Reset All Tabs": "重置所有页面",
    "This will reset ALL custom values in your params.ini. Are you sure?": "这会重置 params.ini 中的全部自定义设置，确定继续吗？",
    "Set Hotkey": "设置快捷键",
    "Press the key or combination of keys you\nwant to use as a hotkey, then click save.": "按下要使用的按键或组合键，\n然后点击保存。",
    "Save": "保存",
    "Cancel": "取消",
    "Yes": "是",
    "No": "否",
    "Discard": "放弃",
    "Favorites": "收藏",
    "Junk": "垃圾",
    "Unmarked": "未标记",
    "English": "英文",
    "Simplified Chinese": "简体中文",
    # Settings categories
    "📦 Loot Behavior": "📦 战利品行为",
    "📄 Profiles": "📄 配置方案",
    "🤖 Automation": "🤖 自动化",
    "🎒 Stash & Transfer": "🎒 储藏箱与转移",
    "🎨 UI & Theme": "🎨 界面与主题",
    "⚙️ System & Paths": "⚙️ 系统与路径",
    "⌨️ Hotkeys": "⌨️ 快捷键",
    "🛠️ Advanced": "🛠️ 高级设置",
    # Setting titles and descriptions
    "Auto-use Temper Manuals": "自动使用淬炼手册",
    "When using the loot filter, should found temper manuals be automatically used? Note: Will not work with stash open.": "运行战利品过滤时，是否自动使用发现的淬炼手册？注意：打开储藏箱时不可用。",
    "Browser": "浏览器",
    "Which browser to use to get builds": "获取构筑数据时使用的浏览器。",
    "Stash Tabs to Filter": "要过滤的储藏箱页",
    "Which stash tabs to check. Note: All tabs available (6 or 7) must be unlocked!": "选择要检查的储藏箱页。注意：所有可用页面（6 或 7 页）都必须已解锁。",
    "Protective Ancestral Filter": "先祖传奇保护",
    "Do not mark ancestral legendaries as junk": "不将先祖传奇装备标记为垃圾。",
    "Full Dump": "完整导入",
    "When using the import build feature, whether to use the full dump (e.g. contains all filter items) or not": "导入构筑时是否生成包含全部过滤物品的完整配置。",
    "Handle Cosmetics": "外观物品处理",
    "What should be done with cosmetic upgrades that do not match any filter": "未匹配任何过滤器的外观升级物品应如何处理。",
    "Unfiltered Unique Behavior": "未匹配暗金处理",
    "What should be done with uniques that do not match any profile. Mythics are always favorited. If mark_as_favorite is unchecked then uniques that match a profile will not be favorited.": "未匹配任何配置方案的暗金装备应如何处理。神话暗金始终会被收藏；若关闭“将匹配物品设为收藏”，匹配方案的暗金也不会被收藏。",
    "Ignore Escalation Sigils": "忽略升级符印",
    "When filtering Sigils, should escalation sigils be ignored?": "过滤符印时是否忽略升级符印。",
    "Aspect Upgrade Handling": "威能升级处理",
    "Whether to keep aspects that didn't match a filter": "是否保留未匹配过滤器的威能。",
    "Interface and Game Language": "界面与游戏语言",
    "Switches both the App interface and the Diablo IV item text/parser language. zhCN remains read-only until its locale data passes the release gate.": "同时切换应用界面和暗黑破坏神 IV 物品文本/解析语言。英文和简体中文均支持受保护的游戏交互。",
    "Switches both the App interface and the Diablo IV item text/parser language. English and Simplified Chinese support guarded game interaction.": "同时切换应用界面和暗黑破坏神 IV 物品文本/解析语言。英文和简体中文均支持受保护的游戏交互。",
    "Weapons": "武器",
    "Non-weapons": "非武器",
    "Vision Mode: Disabled (GUI-only)": "视觉模式：已禁用（仅 GUI）",
    "TTS: Disabled (GUI-only)": "TTS：已禁用（仅 GUI）",
    "Unknown capture error": "未知采集错误",
    "Mark Matched Items as Favorite": "将匹配物品设为收藏",
    "Whether to favorite matched items or not": "是否收藏匹配的物品。",
    "Max Stash Tabs": "储藏箱页数上限",
    "The maximum number of stash tabs available.": "可用储藏箱页数上限。",
    "Overlay Text Size": "浮层文字大小",
    "The minimum font size for the vision overlays.": "视觉浮层使用的最小字号。",
    "Move to Inventory Types": "移入背包的物品类型",
    "When doing stash/inventory transfer, what types of items should be moved": "在储藏箱与背包之间转移时，应移动哪些物品类型。",
    "Move to Stash Types": "移入储藏箱的物品类型",
    "Auto-Start Vision Mode": "自动启动视觉模式",
    "Automatic Failure Capture": "自动保存识别失败样本",
    (
        "When item parsing fails, save a local screenshot and replayable TTS text under "
        "~/.d4lf/captures/automatic. Microphone audio is never recorded; repeated failures are deduplicated."
    ): "物品解析失败时，在 ~/.d4lf/captures/automatic 本地保存截图和可回放的 TTS 文本；"
    "不会录制麦克风音频，同一物品的重复失败会自动去重。",
    "Show Diagnostic Capture Tab": "显示诊断采集标签页",
    (
        "Show the manual raw-TTS diagnostic capture tab in the main window. This developer-oriented tool is "
        "separate from automatic failure capture."
    ): "在主窗口中显示手动原始 TTS 诊断采集标签页。此开发者工具与自动保存识别失败样本相互独立。",
    "Whether to run vision mode on startup or not": "启动 D4LF 时是否运行视觉模式。",
    "Theme": "主题",
    "GUI Theme": "界面主题。",
    "Colorblind Accessible Palette": "色觉辅助配色",
    "Enable colorblind palette": "启用色觉辅助配色。",
    "Vision Mode Type": "视觉模式类型",
    "Should the vision mode use the slightly slower version that highlights matching affixes, or the immediate version that just shows text of the matches? Note: highlight_matches does not work with controllers.": "选择稍慢但可高亮匹配词缀的模式，或只立即显示匹配文本的快速模式。注意：高亮匹配不支持手柄。",
    "Inventory Hotkey": "背包快捷键",
    "Hotkey in Diablo IV to open inventory": "暗黑破坏神 IV 中打开背包的快捷键。",
    "Disable TTS Warning": "禁用 TTS 警告",
    "If TTS is working for you but you are still receiving the warning, check this box to disable it.": "如果 TTS 已正常工作但仍显示警告，可启用此项。",
    "Exit Key": "退出快捷键",
    "Hotkey to exit d4lf": "退出 D4LF 的快捷键。",
    "Fast Vision Mode Coordinates": "快速视觉模式坐标",
    "The top left coordinates of the desired location of the fast vision mode overlay in pixels. For example: (300, 500). Set to blank for default behavior.": "快速视觉模式浮层左上角的像素坐标，例如 (300, 500)。留空则使用默认位置。",
    "Force Refresh Only": "仅强制刷新",
    "Hotkey to refresh the junk/favorite status of all items in your inventory/stash. A filter is not run after.": "刷新背包和储藏箱内所有物品的垃圾/收藏状态，之后不运行过滤器。",
    "Info Overlay": "信息浮层",
    "Hotkey to open/close the info panel overlay": "打开或关闭信息面板浮层的快捷键。",
    "Logging Detail Level": "日志详细级别",
    "The level at which logs are written": "写入日志的最低级别。",
    "Show Timestamps In Logs": "日志显示时间戳",
    "Include timestamps in Dashboard and Full Logs messages. Log files always include timestamps.": "在控制台和完整日志消息中显示时间戳；日志文件始终包含时间戳。",
    "Show Technical Information In Logs": "日志显示技术信息",
    "Include technical information (thread, level, logger name, line number) in Dashboard and Full Logs messages. Log files always include this information.": "在控制台和完整日志中显示线程、级别、记录器名称和行号；日志文件始终包含这些信息。",
    "Move To Chest": "移入储藏箱",
    "Hotkey to move configured items from inventory to stash": "将指定物品从背包移入储藏箱的快捷键。",
    "Move To Inv": "移入背包",
    "Hotkey to move configured items from stash to inventory": "将指定物品从储藏箱移入背包的快捷键。",
    "Diablo IV Process Name": "暗黑破坏神 IV 进程名",
    "The process that is running Diablo 4. You should never need to change this.": "运行暗黑破坏神 IV 的进程名称，通常无需修改。",
    "Run Filter": "运行过滤器",
    "Hotkey to run the filter process. If the item matches no profiles, it is marked as junk.": "运行过滤器的快捷键。未匹配任何配置方案的物品会被标记为垃圾。",
    "Run Filter Drop": "运行过滤并丢弃",
    "Hotkey to run the filter process. If the item matches no profiles, it is dropped.": "运行过滤器的快捷键。未匹配任何配置方案的物品会被丢弃。",
    "Run Filter Force Refresh": "强制刷新后运行过滤",
    "Hotkey to run the filter process with a force refresh. The status of all junk/favorite items will be reset": "强制刷新后运行过滤器的快捷键，所有垃圾/收藏状态都会被重置。",
    "Run Vision Mode": "运行视觉模式",
    "Hotkey to enable/disable the vision mode": "启用或停用视觉模式的快捷键。",
    "Toggle Paragon Overlay": "切换巅峰浮层",
    "Hotkey to open/close the Paragon overlay": "打开或关闭巅峰浮层的快捷键。",
    "Vision Mode Only": "仅视觉模式",
    "Only allow vision mode to run. All hotkeys and actions that click will be disabled.": "仅允许运行视觉模式，并禁用所有会点击游戏的快捷键和操作。",
    # Enum and option labels
    "favorite": "收藏",
    "ignore": "忽略",
    "junk": "垃圾",
    "all": "全部",
    "none": "无",
    "upgrade": "仅升级",
    "common": "普通",
    "legendary": "传奇",
    "magic": "魔法",
    "mythic": "神话",
    "rare": "稀有",
    "set": "套装",
    "unique": "暗金",
    "Common": "普通",
    "Legendary": "传奇",
    "Magic": "魔法",
    "Mythic": "神话",
    "Rare": "稀有",
    "Set": "套装",
    "Unique": "暗金",
    "Value": "数值",
    "Min %": "最低百分比",
    "(No Set Selected)": "（未选择套装）",
    "dungeon": "地下城",
    "affix": "词缀",
    "whitelist": "白名单",
    "blacklist": "黑名单",
    "dark": "深色",
    "light": "浅色",
    "highlight_matches": "高亮匹配",
    "fast": "快速文本",
    "debug": "调试",
    "info": "信息",
    "warning": "警告",
    "error": "错误",
    "critical": "严重",
    # Importer
    "Profile Importer - D2Core / Maxroll / D4Builds / Mobalytics / InfinityBuilds": "配置方案导入 - 暗黑核 / Maxroll / D4Builds / Mobalytics / InfinityBuilds",
    "URL:": "网址：",
    "Generate": "生成",
    "Generating...": "生成中...",
    "Custom file name:": "自定义文件名：",
    "Leave blank for default filename": "留空以使用默认文件名",
    "Default filename includes...": "默认文件名包含...",
    "Source": "来源",
    "Season": "赛季",
    "Class": "职业",
    "Build title": "构筑标题",
    "Variant": "变体",
    "Import Aspect Upgrades": "导入威能升级",
    "Auto-add To Profiles": "自动加入已启用方案",
    "Import GAs": "导入强力词缀",
    "Require all GAs": "要求全部强力词缀",
    "Import Paragon": "导入巅峰盘",
    "If legendary aspects are in the build, do you want an aspect upgrades section generated for them?": "如果构筑中包含传奇威能，是否为其生成威能升级规则？",
    "After import, should the imported file be automatically added to your active profiles?": "导入后是否自动将文件加入已启用的配置方案？",
    "If a build has greater affixes, should they be included in the imported profile?": "构筑包含强力词缀时，是否将其加入导入的配置方案？",
    "If a build has greater affixes, should an item have all of them to be kept?": "构筑包含多个强力词缀时，物品是否必须全部拥有才能保留？",
    "Import Paragon boards into your profile for the integrated Paragon overlay.": "将巅峰盘导入配置方案，以供内置巅峰浮层使用。",
    "Log:": "日志：",
    "Instructions:": "说明：",
    "Enter a URL to generate a profile.": "输入网址以生成配置方案。",
    "Select at least one filename part or enter a custom file name.": "请至少选择一个文件名组成部分，或输入自定义文件名。",
    "Default file name: {summary}": "默认文件名：{summary}",
    "You can link either the build guide or a direct link to the specific planner.": "可以粘贴构筑指南网址，也可以粘贴具体规划器的直接链接。",
    "or": "或",
    "It will create a file based on the label of the build in the planner in: {path}": "将根据规划器中的构筑名称，在以下目录创建文件：{path}",
    "For D4Builds and D2Core you need to specify your browser in the Settings window": "使用 D4Builds 或暗黑核时，需要先在设置窗口中指定浏览器。",
    # Profile editor and common dialogs
    "Profile Editor": "配置方案编辑器",
    "Profile": "配置方案",
    "Undo Changes": "撤销更改",
    "Instructions": "说明",
    "Select a profile from the dropdown. Click 'Save' to save your changes. Click 'Undo Changes' to revert your changes.": "从下拉列表选择配置方案。点击“保存”保存修改，点击“撤销更改”恢复修改。",
    "Unsaved Changes": "有未保存的更改",
    "You have unsaved changes. Do you want to save them before closing?": "存在未保存的更改，关闭前要保存吗？",
    "Alert": "提示",
    "Active Profiles": "已启用的配置方案",
    "Inactive Profiles": "未启用的配置方案",
    "No profiles found": "未找到配置方案",
    "Profile Validation Failed": "配置方案验证失败",
    "Validation Error": "验证错误",
    "Info": "信息",
    "Warning": "警告",
    "Error": "错误",
    "Profile not saved.": "配置方案未保存。",
    "Profile saved successfully to {name}": "配置方案已成功保存到 {name}",
    "The profile model might not be valid. Do you still want to save your changes?": "配置方案模型可能无效，仍要保存更改吗？",
    "Failed to save profile: {error}": "保存配置方案失败：{error}",
    "Affixes": "词缀",
    "Charms": "护身符",
    "Seals": "印记",
    "Aspect Upgrades": "威能升级",
    "Unique Aspects": "暗金特效",
    "Unique Aspects - {names}": "暗金特效 - {names}",
    "Sigils": "符印",
    "Tributes": "贡品",
    "Uniques": "暗金",
    "GlobalUniques": "全局暗金",
    "Remove Selected": "删除所选",
    "Add": "添加",
    "Remove": "删除",
    "Clear": "清空",
    "OK": "确定",
    "Items": "物品",
    "Inherent Pool": "固有词缀池",
    "Affix Pool": "词缀池",
    "Count {count}": "第 {count} 组",
    "Set Min Power": "设置最低物品强度",
    "Min Power:": "最低物品强度：",
    "Set Min Greater Affix": "设置最少强力词缀",
    "Min Greater Affix:": "最少强力词缀：",
    "Set Min Percent Of Affix": "设置词缀最低百分比",
    "Min Percent Of Affix:": "词缀最低百分比：",
    "Create Item": "创建物品",
    "Item Name:": "物品名称：",
    "Delete Items": "删除物品",
    "Select items to delete:": "选择要删除的物品：",
    "Delete Inherent Pool": "删除固有词缀池",
    "Delete Affix Pool": "删除词缀池",
    "Delete Blacklist Sigil": "删除黑名单符印",
    "Delete Whitelist Sigil": "删除白名单符印",
    "Blacklist": "黑名单",
    "Whitelist": "白名单",
    "Select Sigils to delete:": "选择要删除的符印：",
    "Create Sigil": "创建符印",
    "Kind:": "类别：",
    "Name:": "名称：",
    "Type: ": "类型：",
    "Create Tribute": "创建贡品",
    "Tribute:": "贡品：",
    "Tribute: {name}": "贡品：{name}",
    "Add Tribute Rarity": "添加贡品稀有度",
    "Rarity:": "稀有度：",
    "Delete Tributes": "删除贡品",
    "Select Tributes to delete:": "选择要删除的贡品：",
    "None": "无",
    "Add Aspect": "添加威能",
    "Aspect:": "威能：",
    "Create Unique": "创建暗金",
    "Unique Infos": "暗金规则内容",
    "Select info to add to the Unique:": "选择要添加到暗金规则的信息：",
    "Select Item Types": "选择物品类型",
    "Item Types:": "物品类型：",
    "If no item types are selected, all item types will be evaluated for this filter.": "如果未选择物品类型，此过滤器将检查所有物品类型。",
    "Add Affix Pool": "添加词缀池",
    "Add Inherent Pool": "添加固有词缀池",
    "Remove Affix Pool": "删除词缀池",
    "Remove Inherent Pool": "删除固有词缀池",
    "Aspect": "威能",
    "Mode": "模式",
    "Threshold": "阈值",
    "Add Unique Aspect": "添加暗金特效",
    "Remove Unique Aspect": "删除暗金特效",
    "Percent (0-100)": "百分比（0-100）",
    "Value (optional)": "数值（可选）",
    "Min Count:": "最少数量：",
    "Max Count:": "最多数量：",
    "Greater": "强力",
    "Add Affix": "添加词缀",
    "Remove Affix": "删除词缀",
    "Remove Item": "删除物品",
    "Add Sigil": "添加符印",
    "Remove Whitelist Sigil": "删除白名单符印",
    "Remove Blacklist Sigil": "删除黑名单符印",
    "Condition": "条件",
    "Add Condition": "添加条件",
    "Remove Condition": "删除条件",
    "Add Tribute": "添加贡品",
    "Remove Aspect": "删除威能",
    "Auto Sync": "自动同步",
    "Minimum number of checked affixes that must be Greater Affixes.\n0 = Accept items even without GAs (for leveling)\n1-4 = At least this many checked affixes must be GA": "已选词缀中必须为强力词缀的最少数量。\n0 = 没有强力词缀也接受（用于升级）\n1-4 = 至少有对应数量的已选词缀为强力词缀",
    "When checked: Min Greater Affixes automatically matches the number of affixes marked as 'want greater'\nWhen unchecked: You can manually set Min Greater Affixes to any value": "选中时：最低强力词缀数自动匹配标记为“需要强力”的词缀数量\n未选中时：可以手动设置最低强力词缀数",
    "(no greater affixes marked)": "（未标记强力词缀）",
    "(1 greater affix marked)": "（已标记 1 条强力词缀）",
    "({count} greater affixes marked)": "（已标记 {count} 条强力词缀）",
    "Set All Min GAs (Excludes Auto Synced Items)": "设置全部最低强力词缀数（不含自动同步物品）",
    "Convert All To Min %": "全部转换为最低百分比",
    "Set all minPower": "设置全部最低物品强度",
    "Add tribute names and select rarities you want to keep. Leaving rarities empty keeps all rarities.": "添加贡品名称并选择要保留的稀有度；不选择稀有度时将保留全部稀有度。",
    "Add any legendary aspects you'd like to have favorited if an upgrade is found. See the readme on AspectUpgrades for more information.": "添加希望在发现升级时自动收藏的传奇威能。更多信息请参阅 AspectUpgrades 说明。",
    "Select at least one rule to remove.": "请至少选择一条要删除的规则。",
    "Select at least one tribute rule to remove.": "请至少选择一条要删除的贡品规则。",
    "Rarities:": "稀有度：",
    "Priority:": "优先级：",
    "Rarities": "稀有度",
    "All rarities": "全部稀有度",
    "Select Rarities": "选择稀有度",
    "If no rarities are selected, all rarities will be kept for this filter.": "未选择稀有度时，此过滤规则将保留全部稀有度。",
    "Select Sets": "选择套装",
    "Sets": "套装",
    "Sets:": "套装：",
    "Select which sets this charm filter should match.": "选择此护身符过滤规则应匹配的套装。",
    "All item types": "全部物品类型",
    "No sets selected": "未选择套装",
    "Create Charm": "创建护身符",
    "Create Seal": "创建印记",
    "Remove Charm": "删除护身符",
    "Remove Seal": "删除印记",
    "Charm Name:": "护身符名称：",
    "Seal Name:": "印记名称：",
    "Create Rule": "创建规则",
    "Remove Rule": "删除规则",
    "Unique Rule {index}": "暗金规则 {index}",
    "Global Unique Rule": "全局暗金规则",
    "Profile Alias:": "配置方案别名：",
    "Minimum Power:": "最低物品强度：",
    "Min Greater Affixes:": "最低强力词缀数：",
    "Min Percent of Aspect:": "威能最低百分比：",
    "Item name cannot be empty": "物品名称不能为空。",
    "Item name already exist": "物品名称已存在。",
    "Name cannot be empty": "名称不能为空。",
    "Name already exists": "名称已存在。",
    "Select a valid tribute from the list.": "请从列表中选择有效贡品。",
    "Tribute already exist. You can modify the existing one.": "该贡品已存在，可以修改现有规则。",
    "Select a valid rarity from the list.": "请从列表中选择有效稀有度。",
    "Rarity already exists in this tribute filter.": "此贡品过滤规则中已存在该稀有度。",
    "Sigil already exist in whitelist. You can modify the existing one.": "该符印已存在于白名单中，可以修改现有规则。",
    "Sigil already exist in blacklist. You can modify the existing one.": "该符印已存在于黑名单中，可以修改现有规则。",
    "All unique aspects have already been added.": "所有暗金特效都已添加。",
    "Min % must be between 0 and 100.": "最低百分比必须在 0 到 100 之间。",
    "Cannot add unique aspects when sets are selected.": "已选择套装时不能添加暗金特效。",
    "Cannot select sets when unique aspects are defined.": "已定义暗金特效时不能选择套装。",
}

_EN_US_BY_ZH_CN = {translated: source for source, translated in _ZH_CN_TEXT.items() if "{" not in source}


def _template_pattern(template: str) -> re.Pattern[str]:
    parts: list[str] = []
    seen_fields: set[str] = set()
    for literal, field_name, _format_spec, _conversion in Formatter().parse(template):
        parts.append(re.escape(literal))
        if field_name is None:
            continue
        if field_name in seen_fields:
            parts.append(rf"(?P={field_name})")
        else:
            parts.append(rf"(?P<{field_name}>.*?)")
            seen_fields.add(field_name)
    return re.compile("".join(parts), re.DOTALL)


_TEMPLATE_PAIRS = tuple(
    (source, translated, _template_pattern(source), _template_pattern(translated))
    for source, translated in sorted(_ZH_CN_TEXT.items(), key=lambda item: len(item[0]), reverse=True)
    if "{" in source
)


def current_locale() -> str:
    from src.config.loader import IniConfigLoader  # noqa: PLC0415

    return IniConfigLoader().general.language


def translate(source: str, *, locale: str | None = None, **values: object) -> str:
    target_locale = locale or current_locale()
    canonical_source = _EN_US_BY_ZH_CN.get(source, source)
    if canonical_source in _ZH_CN_TEXT:
        translated = _ZH_CN_TEXT[canonical_source] if target_locale == ZH_CN else canonical_source
        return translated.format(**values) if values else translated

    if not values:
        for english, chinese, english_pattern, chinese_pattern in _TEMPLATE_PAIRS:
            match = english_pattern.fullmatch(source) or chinese_pattern.fullmatch(source)
            if match:
                template = chinese if target_locale == ZH_CN else english
                captured_values = {
                    key: translate(value, locale=target_locale) for key, value in match.groupdict().items()
                }
                return template.format(**captured_values)

    return canonical_source.format(**values) if values else canonical_source


def language_label(language: str, *, locale: str | None = None) -> str:
    source = "Simplified Chinese" if language == ZH_CN else "English"
    return f"{translate(source, locale=locale)} ({language})"


def translate_widget_tree(root: QWidget, *, locale: str | None = None) -> None:
    for widget in (root, *root.findChildren(QWidget)):
        if isinstance(widget, QMainWindow | QDialog):
            widget.setWindowTitle(translate(widget.windowTitle(), locale=locale))
        if isinstance(widget, QLabel | QAbstractButton):
            widget.setText(translate(widget.text(), locale=locale))
        elif isinstance(widget, QGroupBox):
            widget.setTitle(translate(widget.title(), locale=locale))
        elif isinstance(widget, QLineEdit):
            if widget.placeholderText():
                widget.setPlaceholderText(translate(widget.placeholderText(), locale=locale))
            if widget.isReadOnly() and widget.text():
                with QSignalBlocker(widget):
                    widget.setText(translate(widget.text(), locale=locale))
        if isinstance(widget, QComboBox) and widget.property("translate_items"):
            with QSignalBlocker(widget):
                for index in range(widget.count()):
                    source = widget.itemData(index)
                    if source is not None:
                        widget.setItemText(index, translate(str(source), locale=locale))
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                widget.setTabText(index, translate(widget.tabText(index), locale=locale))
        if widget.toolTip():
            widget.setToolTip(translate(widget.toolTip(), locale=locale))

    for action in root.findChildren(QAction):
        action.setText(translate(action.text(), locale=locale))
        if action.toolTip():
            action.setToolTip(translate(action.toolTip(), locale=locale))


class UiLocalizationEventFilter(QObject):
    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1 is not None and a1.type() == QEvent.Type.Show and isinstance(a0, QWidget):
            translate_widget_tree(a0)
        return False


def install_ui_localization(app: QApplication) -> UiLocalizationEventFilter:
    existing_filters = app.findChildren(UiLocalizationEventFilter)
    if existing_filters:
        return existing_filters[0]
    event_filter = UiLocalizationEventFilter(app)
    app.installEventFilter(event_filter)
    return event_filter


def retranslate_open_windows(app: QApplication, *, locale: str | None = None) -> None:
    for window in app.topLevelWidgets():
        translate_widget_tree(window, locale=locale)
