"""Official enUS/zhCN Paragon board and glyph display-name catalog."""

from __future__ import annotations

import re
from typing import Literal

from src.gui.i18n import EN_US, ZH_CN

ParagonNameKind = Literal["board", "glyph"]
NamePair = tuple[str, str]

# Paired by IdName from Diablo4Companion commit
# 6e52cac060a5eed18411ba2f70c99a35e765d7cd. The four source files were last
# updated for v3.0.1 and contain the game's enUS and zhCN display strings.
PARAGON_BOARD_NAMES: dict[str, NamePair] = {
    "Paragon_Barb_00": ("Start", "开始"),
    "Paragon_Barb_01": ("Hemorrhage", "出血"),
    "Paragon_Barb_02": ("Blood Rage", "血怒"),
    "Paragon_Barb_03": ("Carnage", "屠戮者"),
    "Paragon_Barb_04": ("Decimator", "残杀者"),
    "Paragon_Barb_05": ("Bone Breaker", "碎骨者"),
    "Paragon_Barb_06": ("Flawless Technique", "无瑕技法"),
    "Paragon_Barb_07": ("Warbringer", "战争使者"),
    "Paragon_Barb_08": ("Weapons Master", "武器大师"),
    "Paragon_Barb_10": ("Force of Nature", "自然之力"),
    "Paragon_Druid_00": ("Start", "开始"),
    "Paragon_Druid_01": ("Thunderstruck", "雷霆打击"),
    "Paragon_Druid_02": ("Earthen Devastation", "大地灭绝"),
    "Paragon_Druid_03": ("Survival Instincts", "生存本能"),
    "Paragon_Druid_04": ("Lust for Carnage", "杀戮欲望"),
    "Paragon_Druid_05": ("Heightened Malice", "恶念加重"),
    "Paragon_Druid_06": ("Inner Beast", "内心的野兽"),
    "Paragon_Druid_07": ("Constricting Tendrils", "紧缩卷须"),
    "Paragon_Druid_08": ("Ancestral Guidance", "先祖指引"),
    "Paragon_Druid_10": ("Untamed", "无羁"),
    "Paragon_Necro_00": ("Start", "开始"),
    "Paragon_Necro_01": ("Cult Leader", "邪信领袖"),
    "Paragon_Necro_02": ("Hulking Monstrosity", "魁梧畸体"),
    "Paragon_Necro_03": ("Flesh-eater", "肉食者"),
    "Paragon_Necro_04": ("Scent of Death", "死亡气息"),
    "Paragon_Necro_05": ("Bone Graft", "骨骼移植"),
    "Paragon_Necro_06": ("Blood Begets Blood", "气血双生"),
    "Paragon_Necro_07": ("Bloodbath", "血浴"),
    "Paragon_Necro_08": ("Wither", "枯萎凋零"),
    "Paragon_Necro_10": ("Frailty", "脆弱"),
    "Paragon_Paladin_00": ("Start", "开始"),
    "Paragon_Paladin_01": ("Castle", "壁垒"),
    "Paragon_Paladin_02": ("Shield Bearer", "负盾者"),
    "Paragon_Paladin_03": ("Fervent", "激昂"),
    "Paragon_Paladin_04": ("Preacher", "布道者"),
    "Paragon_Paladin_05": ("Divinity", "神性"),
    "Paragon_Paladin_06": ("Relentless", "不懈"),
    "Paragon_Paladin_07": ("Sentencing", "裁决"),
    "Paragon_Paladin_08": ("Endure", "坚忍"),
    "Paragon_Paladin_09": ("Beacon", "信标"),
    "Paragon_Rogue_00": ("Start", "开始"),
    "Paragon_Rogue_01": ("Eldritch Bounty", "怪异赏金"),
    "Paragon_Rogue_02": ("Tricks of the Trade", "交易骗术"),
    "Paragon_Rogue_03": ("Cheap Shot", "卑鄙招数"),
    "Paragon_Rogue_04": ("Deadly Ambush", "致命伏击"),
    "Paragon_Rogue_05": ("Leyrana's Instinct", "莱拉娜的本能"),
    "Paragon_Rogue_06": ("No Witnesses", "不留证人"),
    "Paragon_Rogue_07": ("Exploit Weakness", "直击弱点"),
    "Paragon_Rogue_08": ("Cunning Stratagem", "狡诈计谋"),
    "Paragon_Rogue_10": ("Danse Macabre", "死亡之舞"),
    "Paragon_Sorc_00": ("Start", "开始"),
    "Paragon_Sorc_01": ("Searing Heat", "灼烧之热"),
    "Paragon_Sorc_02": ("Frigid Fate", "冰冷命运"),
    "Paragon_Sorc_03": ("Static Surge", "静电奔涌"),
    "Paragon_Sorc_04": ("Elemental Summoner", "元素召唤师"),
    "Paragon_Sorc_05": ("Burning Instinct", "燃烧本能"),
    "Paragon_Sorc_06": ("Icefall", "陨冰"),
    "Paragon_Sorc_07": ("Ceaseless Conduit", "不灭导体"),
    "Paragon_Sorc_08": ("Enchantment Master", "附魔大师"),
    "Paragon_Sorc_10": ("Fundamental Release", "元能释放"),
    "Paragon_Spirit_0": ("Start", "开始"),
    "Paragon_Spirit_01": ("In-Fighter", "见招拆招"),
    "Paragon_Spirit_02": ("Spiney Skin", "多刺棘皮"),
    "Paragon_Spirit_03": ("Viscous Shield", "粘性护盾"),
    "Paragon_Spirit_04": ("Bitter Medicine", "辛烈猛药"),
    "Paragon_Spirit_05": ("Revealing", "攻瑕蹈隙"),
    "Paragon_Spirit_06": ("Drive", "驱动"),
    "Paragon_Spirit_07": ("Convergence", "灵能汇流"),
    "Paragon_Spirit_08": ("Prodigy's Tempo", "奇才节奏"),
    "Paragon_Warlock_00": ("Start", "开始"),
    "Paragon_Warlock_01": ("Fathomless", "无底深潜"),
    "Paragon_Warlock_02": ("Demonic Spicules", "恶魔尖刺"),
    "Paragon_Warlock_03": ("Dynamism", "动力"),
    "Paragon_Warlock_04": ("Pyrosis", "炎灼"),
    "Paragon_Warlock_05": ("Overmind", "主脑"),
    "Paragon_Warlock_06": ("Greater Hex", "强力妖术"),
    "Paragon_Warlock_07": ("Ritualism", "仪祭"),
    "Paragon_Warlock_08": ("Chaos", "混沌"),
    "Paragon_Warlock_10": ("Dominion", "统治"),
}

PARAGON_GLYPH_NAMES: dict[str, NamePair] = {
    "Rare_001_Intelligence_Main": ("Enchanter", "附魔"),
    "Rare_002_Intelligence_Main": ("Unleash", "释放"),
    "Rare_003_Intelligence_Main": ("Elementalist", "元素使"),
    "Rare_004_Intelligence_Main": ("Adept", "娴熟"),
    "Rare_005_Intelligence_Main": ("Conjurer", "咒术师"),
    "Rare_006_Intelligence_Main": ("Charged", "带电"),
    "Rare_007_Willpower_Side": ("Torch", "火炬"),
    "Rare_008_Willpower_Side": ("Pyromaniac", "纵火"),
    "Rare_009_Willpower_Side": ("Cryopathy", "伤寒症"),
    "Rare_010_Dexterity_Main": ("Tactician", "战术家"),
    "Rare_011_Intelligence_Side": ("Guzzler", "暴食者"),
    "Rare_011_Willpower_Side": ("Imbiber", "吸收者"),
    "Rare_012_Intelligence_Side": ("Protector", "保护者"),
    "Rare_012_Willpower_Side": ("Reinforced", "加固"),
    "Rare_013_Dexterity_Side": ("Poise", "镇静"),
    "Rare_014_Dexterity_Side": ("Territorial", "领地"),
    "Rare_014_Strength_Main": ("Turf", "驱逐"),
    "Rare_014_Strength_Side": ("Turf", "驱逐"),
    "Rare_015_Dexterity_Side": ("Flamefeeder", "火焰喂食者"),
    "Rare_016_Dexterity_Side": ("Exploit", "利用"),
    "Rare_016_Intelligence_Side": ("Exploit", "利用"),
    "Rare_016_Strength_Side": ("Exploit", "利用"),
    "Rare_017_Dexterity_Side": ("Winter", "凛冬"),
    "Rare_018_Dexterity_Side": ("Electrocute", "电刑"),
    "Rare_019_Dexterity_Side": ("Destruction", "破坏"),
    "Rare_020_Dexterity_Side": ("Control", "控制"),
    "Rare_020_Intelligence_Main": ("Control", "控制"),
    "Rare_020_Intelligence_Side": ("Control", "控制"),
    "Rare_021_Strength_Main": ("Ambidextrous", "灵巧"),
    "Rare_022_Strength_Main": ("Might", "勇力"),
    "Rare_023_Strength_Main": ("Cleaver", "削砍"),
    "Rare_024_Strength_Main": ("Seething", "恼怒"),
    "Rare_025_Strength_Main": ("Crusher", "碾压者"),
    "Rare_026_Strength_Main": ("Executioner", "处决者"),
    "Rare_027_Strength_Main": ("Ire", "怒火"),
    "Rare_028_Strength_Main": ("Marshal", "统帅"),
    "Rare_029_Dexterity_Side": ("Bloodfeeder", "鲜血喂食者"),
    "Rare_030_Dexterity_Side": ("Wrath", "愤怒"),
    "Rare_031_Dexterity_Side": ("Weapon Master", "武器大师"),
    "Rare_032_Dexterity_Side": ("Mortal Draw", "致命吸引"),
    "Rare_033_Intelligence_Side": ("Revenge", "复仇"),
    "Rare_033_Willpower_Side": ("Revenge", "复仇"),
    "Rare_033_Willpower_Side_Necro": ("Revenge", "复仇"),
    "Rare_034_Intelligence_Side": ("Undaunted", "无惧"),
    "Rare_034_Willpower_Side": ("Undaunted", "无惧"),
    "Rare_035_Intelligence_Side": ("Dominate", "支配"),
    "Rare_035_Willpower_Side": ("Dominate", "支配"),
    "Rare_035_Willpower_Side_Necro": ("Dominate", "支配"),
    "Rare_036_Willpower_Side": ("Disembowel", "开膛破肚"),
    "Rare_037_Willpower_Side": ("Brawl", "搏斗"),
    "Rare_038_Intelligence_Main": ("Corporeal", "有形"),
    "Rare_039_Willpower_Main": ("Fang and Claw", "尖牙和利爪"),
    "Rare_040_Willpower_Main": ("Earth and Sky", "大地天空"),
    "Rare_041_Intelligence_Side": ("Wilds", "狂野"),
    "Rare_042_Willpower_Main": ("Werebear", "熊人"),
    "Rare_043_Willpower_Main": ("Werewolf", "狼人"),
    "Rare_044_Willpower_Main": ("Human", "人类"),
    "Rare_045_Intelligence_Side": ("Bane", "灾星"),
    "Rare_045_Strength_Side": ("Bane", "灾星"),
    "Rare_046_Dexterity_Side": ("Abyssal", "深渊"),
    "Rare_046_Intelligence_Side": ("Keeper", "守卫"),
    "Rare_047_Dexterity_Side": ("Fulminate", "爆雷"),
    "Rare_047_Intelligence_Side": ("Fulminate", "爆雷"),
    "Rare_048_Dexterity_Side": ("Tracker", "追踪者"),
    "Rare_048_Intelligence_Side": ("Tracker", "追踪者"),
    "Rare_049_Dexterity_Side": ("Outmatch", "凌驾"),
    "Rare_049_Strength_Main": ("Outmatch", "凌驾"),
    "Rare_049_Strength_Side": ("Outmatch", "凌驾"),
    "Rare_050_Dexterity_Main": ("Spirit", "灵力"),
    "Rare_050_Dexterity_Side": ("Spirit", "灵力"),
    "Rare_050_Willpower_Side": ("Spirit", "灵力"),
    "Rare_051_Dexterity_Side": ("Shapeshifter", "变形者"),
    "Rare_052_Dexterity_Main": ("Versatility", "随机应变"),
    "Rare_053_Dexterity_Main": ("Closer", "追击者"),
    "Rare_054_Dexterity_Main": ("Ranger", "巡游侠"),
    "Rare_055_Dexterity_Main": ("Chip", "削凿"),
    "Rare_055_Dexterity_Side": ("Chip", "削凿"),
    "Rare_055_Willpower_Side": ("Chip", "削凿"),
    "Rare_056_Dexterity_Main": ("Grenadier", "掷弹兵"),
    "Rare_057_Dexterity_Main": ("Fluidity", "流体"),
    "Rare_058_Intelligence_Side": ("Infusion", "灌魔"),
    "Rare_059_Dexterity_Main": ("Devious", "阴险"),
    "Rare_060_Dexterity_Side": ("Warrior", "战士"),
    "Rare_061_Intelligence_Side": ("Combat", "战斗"),
    "Rare_062_Dexterity_Side": ("Gravekeeper", "守墓人"),
    "Rare_063_Intelligence_Side": ("Canny", "精明"),
    "Rare_064_Intelligence_Side": ("Efficacy", "效能"),
    "Rare_065_Intelligence_Side": ("Snare", "诱捕"),
    "Rare_066_Dexterity_Side": ("Essence", "精魂"),
    "Rare_067_Strength_Side": ("Pride", "骄纵"),
    "Rare_068_Strength_Side": ("Ambush", "伏击"),
    "Rare_069_Intelligence_Main": ("Sacrificial", "牺牲"),
    "Rare_070_Intelligence_Main": ("Blood-drinker", "饮血者"),
    "Rare_071_Intelligence_Main": ("Deadraiser", "死尸复生者"),
    "Rare_072_Intelligence_Main": ("Mage", "法师"),
    "Rare_073_Intelligence_Main": ("Amplify", "增幅"),
    "Rare_074_Willpower_Side": ("Golem", "傀儡"),
    "Rare_075_Willpower_Side": ("Scourge", "煞星"),
    "Rare_076_Strength_Main": ("Diminish", "削弱"),
    "Rare_076_Strength_Side": ("Diminish", "削弱"),
    "Rare_077_Willpower_Side": ("Warding", "界护"),
    "Rare_078_Willpower_Side": ("Darkness", "黑暗"),
    "Rare_079_Dexterity_Side": ("Exploit", "利用"),
    "Rare_080_Strength_Main": ("Twister", "旋风"),
    "Rare_081_Strength_Main": ("Rumble", "轰鸣"),
    "Rare_082_Dexterity_Main": ("Explosive", "爆炸"),
    "Rare_083_Intelligence_Side": ("Nightstalker", "夜行者"),
    "Rare_084_Intelligence_Main": ("Stalagmite", "石笋"),
    "Rare_085_Dexterity_Side": ("Invocation", "祈告"),
    "Rare_086_Dexterity_Side": ("Tectonic", "地动"),
    "Rare_087_Willpower_Main": ("Electrocution", "电刑"),
    "Rare_088_Intelligence_Main": ("Exhumation", "掘墓"),
    "Rare_089_Willpower_Side": ("Desecration", "亵渎"),
    "Rare_090_Dexterity_Main": ("Menagerist", "御灵师"),
    "Rare_091_Strength_Side": ("Hone", "砥砺"),
    "Rare_092_Intelligence_Side": ("Consumption", "腐化消解"),
    "Rare_093_Dexterity_Main": ("Fitness", "健硕"),
    "Rare_094_Intelligence_Side": ("Ritual", "仪祭"),
    "Rare_095_Dexterity_Main": ("Jagged Plume", "锐羽"),
    "Rare_096_Strength_Side": ("Innate", "天生神力"),
    "Rare_097_Dexterity_Main": ("Wildfire", "野火"),
    "Rare_098_Strength_Side": ("Colossal", "猛力"),
    "Rare_100_Dexterity_Main": ("Talon", "掠爪"),
    "Rare_101_Strength_Side": ("Hubris", "嚣狂"),
    "Rare_102_Dexterity_Main": ("Fester", "腐溃"),
    "Rare_103_Strength_Main": ("Sentinel", "守备"),
    "Rare_104_Dexterity_Side": ("Honed", "修磨"),
    "Rare_105_Strength_Main": ("Law", "律法"),
    "Rare_106_Strength_Main": ("Retribution", "惩戒"),
    "Rare_106_Willpower_Side": ("Arbiter", "仲裁官"),
    "Rare_107_Strength_Main": ("Resplendence", "辉煌"),
    "Rare_108_Intelligence_Side": ("Judicator", "审判者"),
    "Rare_109_Dexterity_Side": ("Feverous", "热忱者"),
    "Rare_110_Strength_Main": ("Apostle", "使徒"),
    "Rare_111_Willpower_Main": ("Blood Frenzy", "血性狂乱"),
    "Rare_112_Willpower_Main": ("Eliminator", "灭除者"),
    "Rare_113_Willpower_Main": ("Death Aura", "死亡光环"),
    "Rare_114_Intelligence_Side": ("Occultist", "秘术师"),
    "Rare_115_Intelligence_Side": ("Unbound", "解禁"),
    "Rare_116_Intelligence_Side": ("Hellforge", "地狱熔炉"),
    "Rare_117_Strength_Side": ("Abyssal", "深渊"),
    "Rare_118_Willpower_Main": ("Ichor Carapace", "脓腐甲壳"),
    "Rare_119_Strength_Side": ("Wrath", "愤怒"),
    "Rare_120_Willpower_Main": ("Eldritch Sight", "邪视"),
    "Rare_121_Intelligence_Side": ("Entropy", "熵能"),
    "Rare_122_Willpower_Main": ("Vanguard", "先锋"),
    "Rare_123_Willpower_Main": ("Mastermind", "战术大师"),
    "Rare_124_Willpower_Main": ("Archfiend", "高等恶魔"),
    "Rare_125_Willpower_Main": ("Control", "控制"),
    "Rare_126_Strength_Side": ("Destruction", "破坏"),
    "Rare_127_Intelligence_Side": ("Attrition", "损耗"),
    "Rare_128_Strength_Side": ("Demonologist", "恶魔学家"),
    "Rare_129_Strength_Side": ("Empowered", "强能"),
    "Rare_130_Dexterity_Main": ("Volley", "箭幕"),
    "Rare_131_Intelligence_Side": ("Eclipse", "日食"),
    "Rare_132_Strength_Side": ("Assassin", "刺客"),
    "Rare_Dex_Generic": ("Headhunter", "猎头者"),
    "Rare_Int_Generic": ("Eliminator", "灭除者"),
    "Rare_Str_Generic": ("Challenger", "挑战者"),
    "Rare_Will_Generic": ("Headhunter", "猎头者"),
}

# d4data 3.1.1 commit 5b68e74dc0a54f03cce81e0591a3a29a48a1a694 moved
# Tactician from *_Main to *_Side and pluralized Golem. The zhCN names below
# reuse the official strings already paired to those same glyph identities.
_CURRENT_GLYPH_ID_ALIASES: dict[str, NamePair] = {"Rare_010_Dexterity_Side": ("Tactician", "战术家")}
_BOARD_NAME_ALIASES: dict[str, NamePair] = {
    "Starting Board": ("Starting Board", "开始"),
    "Starter Board": ("Starter Board", "开始"),
}
_GLYPH_NAME_ALIASES: dict[str, NamePair] = {"Golems": ("Golems", "傀儡")}

_BOARD_CLASS_BY_ID_PREFIX = {
    "paragonbarb": "barbarian",
    "paragondruid": "druid",
    "paragonnecro": "necromancer",
    "paragonpaladin": "paladin",
    "paragonrogue": "rogue",
    "paragonsorc": "sorcerer",
    "paragonspirit": "spiritborn",
    "paragonwarlock": "warlock",
}


def _normalize_identifier(value: object) -> str:
    text = str(value or "").strip().rsplit("::", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _normalize_name(value: object) -> str:
    text = re.sub(r"^glyph:\s*", "", str(value or "").strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _id_index(records: dict[str, NamePair], aliases: dict[str, NamePair] | None = None) -> dict[str, NamePair]:
    combined = records if aliases is None else records | aliases
    return {_normalize_identifier(identifier): pair for identifier, pair in combined.items()}


def _name_indexes(
    records: dict[str, NamePair], aliases: dict[str, NamePair]
) -> tuple[dict[str, NamePair], dict[str, tuple[NamePair, ...]]]:
    english: dict[str, NamePair] = {}
    chinese: dict[str, set[NamePair]] = {}
    for pair in (*records.values(), *aliases.values()):
        english.setdefault(_normalize_name(pair[0]), pair)
        chinese.setdefault(pair[1], set()).add(pair)
    return english, {name: tuple(sorted(pairs)) for name, pairs in chinese.items()}


_BOARD_BY_ID = _id_index(PARAGON_BOARD_NAMES)
_GLYPH_BY_ID = _id_index(PARAGON_GLYPH_NAMES, _CURRENT_GLYPH_ID_ALIASES)
_BOARD_BY_ENGLISH, _BOARD_BY_CHINESE = _name_indexes(PARAGON_BOARD_NAMES, _BOARD_NAME_ALIASES)
_GLYPH_BY_ENGLISH, _GLYPH_BY_CHINESE = _name_indexes(PARAGON_GLYPH_NAMES, _GLYPH_NAME_ALIASES)


def paragon_board_class_slug(identifier: object) -> str | None:
    """Resolve a D4LF class slug from any supported board-ID spelling."""
    normalized = _normalize_identifier(identifier)
    return next(
        (class_slug for prefix, class_slug in _BOARD_CLASS_BY_ID_PREFIX.items() if normalized.startswith(prefix)), None
    )


def translate_paragon_name(source: object, *, kind: ParagonNameKind, locale: str, identifier: object = None) -> str:
    """Translate a board/glyph proper name, preferring its stable game ID."""
    text = str(source or "").strip()
    by_id = _BOARD_BY_ID if kind == "board" else _GLYPH_BY_ID
    pair = by_id.get(_normalize_identifier(identifier))
    if pair is not None:
        return pair[1] if locale == ZH_CN else pair[0]

    by_english = _BOARD_BY_ENGLISH if kind == "board" else _GLYPH_BY_ENGLISH
    pair = by_english.get(_normalize_name(text))
    if pair is not None:
        return pair[1] if locale == ZH_CN else pair[0]

    by_chinese = _BOARD_BY_CHINESE if kind == "board" else _GLYPH_BY_CHINESE
    chinese_matches = by_chinese.get(text, ())
    if locale == ZH_CN and chinese_matches:
        return text
    if locale == EN_US and len(chinese_matches) == 1:
        return chinese_matches[0][0]

    return text
