import sys
from types import SimpleNamespace
from typing import cast

import pytest

if sys.platform != "win32":
    pytest.skip("Windows-only overlay test", allow_module_level=True)

from src.config.profile_models import ParagonPayloadModel
from src.gui.i18n import EN_US, ZH_CN, translate
from src.paragon_names import PARAGON_BOARD_NAMES, PARAGON_GLYPH_NAMES, paragon_board_class_slug, translate_paragon_name
from src.paragon_overlay import (
    ParagonOverlay,
    _format_build_display_name,
    _translate_step_suffix,
    format_board_display_text,
    load_builds_from_path,
)


def test_load_builds_from_path_uses_typed_paragon_payloads(monkeypatch):
    payload = ParagonPayloadModel.model_validate({
        "Name": "Build Name",
        "ParagonBoardsList": [
            [{"Name": "Starting Board", "Glyph": "glyph_name", "Rotation": 0, "Nodes": [False] * 441}],
            [{"Name": "Second Step Board", "Glyph": "glyph_name", "Rotation": 90, "Nodes": [False] * 441}],
        ],
    })

    monkeypatch.setattr("src.item.filter.Filter.get_paragon_filters", lambda _self: {"profile_name": payload})

    builds = load_builds_from_path()

    assert [build["name"] for build in builds] == ["Build Name - Step 2", "Build Name - Step 1"]
    assert builds[0]["boards"][0].rotation == "90°"
    assert builds[1]["boards"][0].rotation == "0°"
    assert (
        format_board_display_text(builds[0]["boards"][0]) == "Second Step Board - Second Step Board - Glyph Name - 90°"
    )


@pytest.mark.parametrize(
    ("source", "translated"),
    [
        ("D4LF Paragon Overlay", "D4LF 巅峰浮层"),
        ("Paragon", "巅峰盘"),
        ("Compact View", "紧凑视图"),
        ("Full View", "完整视图"),
        ("Settings⚙ ▼", "设置⚙ ▼"),
        ("Builds ▼", "构筑 ▼"),
        ("Grid locked", "网格已锁定"),
        ("Grid unlocked", "网格未锁定"),
        ("Golden frames (on)", "金色边框（开）"),
        ("Golden frames (off)", "金色边框（关）"),
        ("Reload profiles", "重新加载配置方案"),
        ("Reset grid defaults", "恢复网格默认设置"),
        ("Grid Zoom", "网格缩放"),
        ("Move\nGrid", "移动\n网格"),
        ("Barbarian", "野蛮人"),
        ("Druid", "德鲁伊"),
        ("Necromancer", "死灵法师"),
        ("Rogue", "游侠"),
        ("Sorcerer", "巫师"),
        ("Spiritborn", "灵巫"),
        ("Paladin", "圣骑士"),
        ("Warlock", "术士"),
    ],
)
def test_paragon_overlay_text_is_bilingual(source, translated):
    assert translate(source, locale=ZH_CN) == translated
    assert translate(translated, locale=EN_US) == source


@pytest.mark.parametrize(
    ("board_name", "glyph_name", "expected"),
    [
        ("sorcerer-start", "", "巫师 - 开始 - 无雕文 - 0°"),
        ("sorcerer-start", "sorcerer-pyromaniac", "巫师 - 开始 - 纵火 - 0°"),
        ("sorcerer-burning-instinct", "sorcerer-flamefeeder", "巫师 - 燃烧本能 - 火焰喂食者 - 0°"),
        ("sorcerer-enchantment-master", "sorcerer-elementalist", "巫师 - 附魔大师 - 元素使 - 0°"),
        ("sorcerer-frigid-fate", "sorcerer-reinforced", "巫师 - 冰冷命运 - 加固 - 0°"),
        ("sorcerer-fundamental-release", "sorcerer-adept", "巫师 - 元能释放 - 娴熟 - 0°"),
        ("sorcerer-static-surge", "sorcerer-tactician", "巫师 - 静电奔涌 - 战术家 - 0°"),
    ],
)
def test_format_board_display_text_localizes_imported_sorcerer_data(board_name, glyph_name, expected):
    payload = ParagonPayloadModel.model_validate({
        "Name": "Build Name",
        "ParagonBoardsList": [[{"Name": board_name, "Glyph": glyph_name, "Rotation": 0, "Nodes": [False] * 441}]],
    })
    board = payload.paragon_boards_list[0][0]

    assert format_board_display_text(board, locale=ZH_CN) == expected


def test_format_board_display_text_preserves_english_output():
    payload = ParagonPayloadModel.model_validate({
        "Name": "Build Name",
        "ParagonBoardsList": [
            [
                {
                    "Name": "sorcerer-burning-instinct",
                    "Glyph": "sorcerer-flamefeeder",
                    "Rotation": 90,
                    "Nodes": [False] * 441,
                }
            ]
        ],
    })

    assert (
        format_board_display_text(payload.paragon_boards_list[0][0], locale=EN_US)
        == "Sorcerer - Burning Instinct - Flamefeeder - 90°"
    )


def test_paragon_catalog_has_complete_companion_id_coverage():
    assert len(PARAGON_BOARD_NAMES) == 79
    assert len(PARAGON_GLYPH_NAMES) == 160
    assert len({pair[0] for pair in PARAGON_BOARD_NAMES.values()}) == 72
    assert len({pair[0] for pair in PARAGON_GLYPH_NAMES.values()}) == 133
    assert all(english and chinese for english, chinese in PARAGON_BOARD_NAMES.values())
    assert all(english and chinese for english, chinese in PARAGON_GLYPH_NAMES.values())


@pytest.mark.parametrize(("identifier", "names"), PARAGON_BOARD_NAMES.items())
def test_every_paragon_board_id_switches_between_official_names(identifier, names):
    english, chinese = names

    assert translate_paragon_name("ignored", kind="board", locale=ZH_CN, identifier=identifier) == chinese
    assert translate_paragon_name("ignored", kind="board", locale=EN_US, identifier=identifier) == english
    assert translate_paragon_name(english, kind="board", locale=ZH_CN) == chinese


@pytest.mark.parametrize(("identifier", "names"), PARAGON_GLYPH_NAMES.items())
def test_every_paragon_glyph_id_switches_between_official_names(identifier, names):
    english, chinese = names

    assert translate_paragon_name("ignored", kind="glyph", locale=ZH_CN, identifier=identifier) == chinese
    assert translate_paragon_name("ignored", kind="glyph", locale=EN_US, identifier=identifier) == english
    assert translate_paragon_name(english, kind="glyph", locale=ZH_CN) == chinese


@pytest.mark.parametrize(
    ("board_name", "board_id", "glyph_name", "glyph_id", "expected"),
    [
        ("unknown", "Paragon_Barb_10", "unknown", "Rare_021_Strength_Main", "野蛮人 - 自然之力 - 灵巧 - 0°"),
        ("unknown", "Paragon_Druid_01", "unknown", "Rare_039_Willpower_Main", "德鲁伊 - 雷霆打击 - 尖牙和利爪 - 0°"),
        ("unknown", "Paragon_Necro_03", "unknown", "Rare_062_Dexterity_Side", "死灵法师 - 肉食者 - 守墓人 - 0°"),
        ("unknown", "Paragon_Rogue_05", "unknown", "Rare_053_Dexterity_Main", "游侠 - 莱拉娜的本能 - 追击者 - 0°"),
        ("unknown", "Paragon_Sorc_10", "unknown", "Rare_004_Intelligence_Main", "巫师 - 元能释放 - 娴熟 - 0°"),
        ("unknown", "Paragon_Spirit_02", "unknown", "Rare_095_Dexterity_Main", "灵巫 - 多刺棘皮 - 锐羽 - 0°"),
        ("unknown", "Paragon_Paladin_01", "unknown", "Rare_106_Willpower_Side", "圣骑士 - 壁垒 - 仲裁官 - 0°"),
        ("unknown", "Paragon_Warlock_10", "unknown", "Rare_116_Intelligence_Side", "术士 - 统治 - 地狱熔炉 - 0°"),
    ],
)
def test_board_cards_use_stable_ids_for_every_supported_class(board_name, board_id, glyph_name, glyph_id, expected):
    payload = ParagonPayloadModel.model_validate({
        "Name": "Build Name",
        "ParagonBoardsList": [
            [
                {
                    "Name": board_name,
                    "BoardId": board_id,
                    "Glyph": glyph_name,
                    "GlyphId": glyph_id,
                    "Rotation": 0,
                    "Nodes": [False] * 441,
                }
            ]
        ],
    })

    assert format_board_display_text(payload.paragon_boards_list[0][0], locale=ZH_CN) == expected


def test_current_d4data_glyph_aliases_remain_localized():
    assert (
        translate_paragon_name("unknown", kind="glyph", locale=ZH_CN, identifier="glyph::rare-010-dexterity-side")
        == "战术家"
    )
    assert translate_paragon_name("Golems", kind="glyph", locale=ZH_CN) == "傀儡"


def test_name_fallback_handles_source_punctuation_and_starting_board_aliases():
    assert translate_paragon_name("Leyranas Instinct", kind="board", locale=ZH_CN) == "莱拉娜的本能"
    assert translate_paragon_name("Flesh Eater", kind="board", locale=ZH_CN) == "肉食者"
    assert translate_paragon_name("Starting Board", kind="board", locale=ZH_CN) == "开始"
    assert translate_paragon_name("Starter Board", kind="board", locale=ZH_CN) == "开始"


def test_name_reverse_translation_uses_kind_and_preserves_ambiguous_glyph():
    assert translate_paragon_name("武器大师", kind="board", locale=EN_US) == "Weapons Master"
    assert translate_paragon_name("武器大师", kind="glyph", locale=EN_US) == "Weapon Master"
    assert translate_paragon_name("仪祭", kind="board", locale=EN_US) == "Ritualism"
    assert translate_paragon_name("仪祭", kind="glyph", locale=EN_US) == "Ritual"
    assert translate_paragon_name("电刑", kind="glyph", locale=EN_US) == "电刑"
    assert (
        translate_paragon_name("电刑", kind="glyph", locale=EN_US, identifier="Rare_018_Dexterity_Side")
        == "Electrocute"
    )
    assert (
        translate_paragon_name("电刑", kind="glyph", locale=EN_US, identifier="Rare_087_Willpower_Main")
        == "Electrocution"
    )


@pytest.mark.parametrize(
    ("identifier", "class_slug"),
    [
        ("paragon-board::paragon-barb-10", "barbarian"),
        ("Paragon_Druid_01", "druid"),
        ("Paragon_Necro_03", "necromancer"),
        ("Paragon_Rogue_05", "rogue"),
        ("Paragon_Sorc_10", "sorcerer"),
        ("Paragon_Spirit_02", "spiritborn"),
        ("Paragon_Paladin_01", "paladin"),
        ("Paragon_Warlock_10", "warlock"),
    ],
)
def test_paragon_board_class_slug_supports_all_classes(identifier, class_slug):
    assert paragon_board_class_slug(identifier) == class_slug


def test_generated_step_suffix_switches_language_without_translating_build_name():
    assert _translate_step_suffix("Firewall - Step 2", locale=ZH_CN) == "Firewall - 阶段 2"
    assert _translate_step_suffix("Firewall - Step 2", locale=EN_US) == "Firewall - Step 2"
    assert _format_build_display_name("infinitybuilds_sorcerer_Firewall - Step 2", locale=ZH_CN) == "Firewall - 阶段 2"


def test_language_config_change_schedules_live_paragon_refresh(monkeypatch):
    language_refresh = object()
    color_refresh = object()
    overlay = cast(
        "ParagonOverlay",
        SimpleNamespace(_apply_live_language_change=language_refresh, _apply_live_colorblind_change=color_refresh),
    )
    scheduled = []
    monkeypatch.setattr("src.paragon_overlay.post_to_ui_thread", scheduled.append)

    ParagonOverlay._on_config_changed(overlay, {"general.language"})

    assert scheduled == [language_refresh]
