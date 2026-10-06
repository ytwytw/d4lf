import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.game_data import GameCatalog, ItemType
from src.game_data import catalog as catalog_module

ROOT = Path(__file__).parents[2]
LOCALE = ROOT / "assets/lang/zhCN"
UNIQUE_NAMES = {
    "ancients_pledge": "先祖之誓",
    "annihilus": "毁灭",
    "bell_of_the_bovine": "魔牛之铃",
    "call_to_arms": "战斗召唤",
    "edge": "锐锋",
    "enigma": "谜团",
    "grief": "悔恨",
    "hellfire_torch": "地狱火炬",
    "holy_thunder": "圣雷",
    "infinity": "无限",
    "insight": "眼光",
    "kings_grace": "王恩",
    "leaf": "叶子",
    "leorics_crown": "李奥瑞克的王冠",
    "lore": "学识",
    "messerschmidts_reaver": "梅塞施密特的劫掠者",
    "pattern": "典范",
    "phoenix": "凤凰",
    "prudence": "谨慎",
    "rain": "暴雨",
    "spirit": "灵力",
    "stealth": "潜行",
    "strength": "力量",
    "zephyr": "和风",
}
AFFIX_NAMES = {
    "bonus_experience": "奖励经验值",
    "can_equip_more_unique_charm": "可额外装备 个暗金神符",
    "chance_for_an_extra_item_from_the_purveyor_of_curiosities": "几率从珍品商处额外获得一件物品",
    "deadly_strike_chance": "致命打击几率",
    "faster_cast_rate": "更快施法速度",
    "lucky_hit_up_to_a_chance_to_deliver_a_crushing_blow": "幸运一击: 最多有 几率造成粉碎一击",
    "mondays_now_count_as_tuesdays": "现在星期一也算作星期二",
    "primary_resource_on_kill": "击杀回复主要资源",
    "to_shout_skills": "至吼叫技能",
}


@pytest.fixture
def zhcn_catalog(monkeypatch) -> GameCatalog:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(catalog_module, "get_settings", lambda: settings)
    catalog = object.__new__(GameCatalog)
    catalog.load_data()
    return catalog


@pytest.mark.parametrize(("canonical", "name"), UNIQUE_NAMES.items())
def test_upstream_uniques_resolve_chinese_and_preserve_metadata(zhcn_catalog, canonical, name) -> None:
    english = json.loads((ROOT / "assets/lang/enUS/uniques.json").read_text(encoding="utf-8"))

    if canonical == "ancients_pledge":
        assert zhcn_catalog.resolve_unique(name) is None
        assert zhcn_catalog.resolve_unique(name, item_type=ItemType.Shield) == canonical
    else:
        assert zhcn_catalog.resolve_unique(name) == canonical
    assert zhcn_catalog.resolve_unique(canonical) == canonical
    assert zhcn_catalog.aspect_unique_dict[canonical]["num_inherents"] == english[canonical]["num_inherents"]


@pytest.mark.parametrize(("canonical", "name"), AFFIX_NAMES.items())
def test_upstream_affixes_resolve_chinese_exactly(zhcn_catalog, canonical, name) -> None:
    assert zhcn_catalog.resolve_affix_exact(name) == canonical
    assert zhcn_catalog.resolve_affix_exact(canonical) == canonical


def test_upstream_sigil_name_and_complete_description_resolve(zhcn_catalog) -> None:
    assert zhcn_catalog.resolve_sigil("往昔之旅", "dungeons") == "a_journey_through_the_past"
    assert zhcn_catalog.resolve_sigil("暴躁外皮的回响", "positive") == "echo_of_pindleskin"
    text = "暴躁外皮的回响 暴躁外皮的回响在这座地下城中游荡，消灭它时可能掉落游戏中的任意物品。"
    assert zhcn_catalog.resolve_sigil(text, "positive") == "echo_of_pindleskin"
    assert "missing description" not in zhcn_catalog.affix_sigil_dict_all["dungeons"]["a_journey_through_the_past"]


def test_parameterized_resistance_keeps_explicit_english_fallback(zhcn_catalog) -> None:
    selected = json.loads((LOCALE / "affixes.json").read_text(encoding="utf-8"))
    quality = json.loads((LOCALE / "quality-report.json").read_text(encoding="utf-8"))

    assert "resistance" not in selected
    assert zhcn_catalog.affix_dict["resistance"] == "resistance"
    assert zhcn_catalog.resolve_affix_exact("resistance") == "resistance"
    assert zhcn_catalog.resolve_affix_exact("抗性") is None
    assert any(row["stable_id"] == "affixes:resistance" for row in quality["unresolved"])


def test_ancients_unique_name_needs_sourced_item_type(zhcn_catalog) -> None:
    manifest = json.loads((LOCALE / "manifest.json").read_text(encoding="utf-8"))
    records = {row["stable_id"]: row for row in manifest["records"]}
    assert zhcn_catalog.resolve_unique("先祖之誓") is None
    assert zhcn_catalog.resolve_unique("先祖之誓", item_type=ItemType.Axe2H) == "ancients_oath"
    assert zhcn_catalog.resolve_unique("先祖之誓", item_type=ItemType.Sword) is None
    for item_type in (ItemType.Focus, ItemType.OffHandTotem, ItemType.Shield):
        assert zhcn_catalog.resolve_unique("先祖之誓", item_type=item_type) == "ancients_pledge"
    for canonical in ("ancients_oath", "ancients_pledge"):
        source = records["uniques:" + canonical]["metadata_source"]
        types = zhcn_catalog.aspect_unique_dict[canonical]["item_types"]
        assert sorted({entry["runtime_item_type"] for entry in source["source_entries"]}) == types
        encoded = json.dumps(types, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        assert hashlib.sha256(encoded).hexdigest() == source["value_sha256"]


def test_upstream_translation_manifest_binds_locked_sources_and_runtime_text() -> None:
    manifest = json.loads((LOCALE / "manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((LOCALE / "quality-report.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "assets/catalog/source-lock.json").read_text(encoding="utf-8"))
    reviewed_path = ROOT / "src/tools/data/reviewed_zhCN.json"
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))["records"]
    expected = {
        *(f"uniques:{key}" for key in UNIQUE_NAMES),
        *(f"affixes:{key}" for key in AFFIX_NAMES),
        "sigils:dungeons:a_journey_through_the_past",
        "sigils:positive:echo_of_pindleskin",
    }
    delta = quality["upstream_locale_delta"]
    assert delta["added_canonical_records"] == 36
    assert set(delta["resolved_records"]) == expected
    assert delta["unresolved_records"] == ["affixes:resistance"]
    assert quality["summary"]["source_records"] == len(manifest["records"]) + len(quality["unresolved"])
    assert hashlib.sha256(reviewed_path.read_bytes()).hexdigest() == manifest["reviewed_overrides"]["sha256"]
    for entry in manifest["files"]:
        payload = (LOCALE / entry["path"]).read_bytes()
        assert b"\r\n" not in payload
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
    for row in manifest["records"]:
        if row["stable_id"] not in expected:
            continue
        namespace, *keys = row["stable_id"].split(":")
        value = json.loads((LOCALE / f"{namespace}.json").read_text(encoding="utf-8"))
        english = json.loads((ROOT / f"assets/lang/enUS/{namespace}.json").read_text(encoding="utf-8"))
        for key in keys:
            value = value[key]
            english = english[key]
        if namespace == "uniques":
            value = value["display_name"]
            english = keys[0].replace("_", " ")
        assert value == row["text"] == reviewed[row["stable_id"]]
        assert hashlib.sha256(english.encode()).hexdigest() == row["source_sha256"]
        source = row["translation_source"]
        assert hashlib.sha256(value.encode()).hexdigest() == source["translation_sha256"]
        locked = lock["sources"][source["reference_provider"]]
        assert len(source["reference_files"]) == 2
        for reference in source["reference_files"]:
            assert reference["sha256"] in {entry["sha256"] for entry in locked["files"].values()}
            if source["reference_provider"] == "diablo4_companion":
                assert locked["commit"] in reference["url"]
            else:
                assert reference["url"] in {entry["url"] for entry in locked["files"].values()}
        assert source["source_entries"]
        for evidence in source["source_entries"]:
            assert evidence["id"]
            assert evidence["key"]
            assert len(evidence["english_record_sha256"]) == len(evidence["chinese_record_sha256"]) == 64
            text = evidence["chinese_text"]
            if source["transform"] == "name_space_description":
                text += " " + evidence["chinese_description"]
            assert text == value
