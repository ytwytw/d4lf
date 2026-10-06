import pytest

from src.inventory_dump.observations import ambient_only, observe_favorite, observe_item_fields


def test_observed_unknown_unique_retains_literal_fields_without_catalog_mapping() -> None:
    lines = [
        "[收藏物品]. 李奥瑞克的王冠\u00a0",
        "先祖暗金头盔",
        "900 物品强度",
        "1,603 护甲值 （-14.7% 坚韧）",
        "+151 点意力",
        "+16 资源上限 [15 - 20]",
        "+4.8% 攻击速度 [4.4 - 10.0]%",
        "该物品视作首饰，并使镶嵌在此头盔中的任意宝石效果提高 40%[x] [35 - 50]%",
        "空插槽",
        "空插槽",
        "需要等级: 70. 账号绑定. 装备唯一",
        "出售价格:  147,885 金币",
        "耐久度: 100/100. 回火： 4/4",
        "鼠标右键",
    ]
    result = observe_item_fields(lines)
    assert result["name_text"] == "李奥瑞克的王冠"
    assert result["type_text"] == "先祖暗金头盔"
    assert result["item_power"] == 900
    assert result["required_level"] == 70
    assert result["quantity"] is None
    assert result["catalog_mapped"] is False
    assert result["modifier_lines"] == lines[4:7]
    assert result["description_lines"] == lines[2:]
    assert result["empty_socket_mentions"] == 2
    assert result["sell_value"] == 147885
    assert result["durability"] == {"numerator": 100, "denominator": 100, "text": "耐久度: 100/100"}
    assert result["tempering"] == {"numerator": 4, "denominator": 4, "text": "回火： 4/4"}
    assert "affixes" not in result


def test_english_quantity_and_missing_fields_remain_literal() -> None:
    result = observe_item_fields(["NEW KEY", "Lair Boss Key", "Quantity: 1,200", "Account Bound"])
    assert result["quantity"] == 1200
    assert result["item_power"] is None
    assert result["required_level"] is None
    assert result["durability"] is None
    assert result["binding_text"] == ["Account Bound"]


@pytest.mark.parametrize("line", ["Höpe | 70 (133)", "&lt;POTATO&gt; Nadjia | 70 (174)", "Hestia | 70 (176) (1)"])
def test_town_player_broadcasts_are_ambient(line) -> None:
    assert ambient_only([line])


@pytest.mark.parametrize(
    "lines",
    [
        ["电池充电中"],
        ["电池放电中"],
        ["电池充电中", "电池放电中"],
        ["电池充电中", "电池充电中"],
        ["电池充电中", "Höpe | 70 (133)"],
    ],
)
def test_observed_battery_notification_only_is_ambient(lines) -> None:
    # The zhcn.4 live scan and manual diagnostic capture contain these exact non-item notifications.
    assert ambient_only(lines)


@pytest.mark.parametrize(
    "lines",
    [
        ["电池充电中", "谜团", "先祖 神话暗金胸甲", "900 物品强度"],
        ["谜团", "先祖 神话暗金胸甲", "电池充电中"],
        ["电池充电中", "900 物品强度"],
        ["电池充电中", "未知系统通知"],
        ["电池放电中", "谜团", "先祖 神话暗金胸甲"],
        ["电池电量低"],
        ["电池放电中的物品"],
        ["电池充电中的物品"],
        ["电池充电中", ""],
    ],
)
def test_battery_notification_never_erases_item_or_unknown_text(lines) -> None:
    original = list(lines)
    assert not ambient_only(lines)
    assert lines == original


@pytest.mark.parametrize(
    "lines", [[], ["未知钥匙数量 3"], ["新物品", "先祖暗金头盔"], ["Höpe | 70 (133)", "900 物品强度"]]
)
def test_unknown_or_incomplete_item_lines_are_never_classed_as_ambient(lines) -> None:
    assert not ambient_only(lines)


def test_quality_and_unsigned_percentages_are_literal_not_affix_classifications() -> None:
    lines = [
        "示例头盔",
        "先祖暗金头盔",
        "900 物品强度",
        "25（+25）品质",
        "2,004 护甲值",
        "14.0% 冷却时间缩减 [5.0 - 8.0]%",
        "+2,250 生命上限",
    ]
    result = observe_item_fields(lines)
    assert result["quality"] == {"value": 25, "bonus": 25, "text": "25（+25）品质"}
    assert result["modifier_lines"] == lines[5:]
    assert result["description_lines"] == lines[2:]
    assert "affixes" not in result


@pytest.mark.parametrize("line", ["25品质", "25（25）品质", "品质未知", "以25品质升级"])
def test_quality_does_not_infer_missing_bonus_or_parse_prose(line: str) -> None:
    assert observe_item_fields(["示例头盔", "先祖暗金头盔", line])["quality"] is None


@pytest.mark.parametrize("title", ["[收藏物品]. 谜团", "[FAVORITED ITEM]. Unknown item"])
def test_favorite_requires_explicit_current_title_marker(title) -> None:
    lines = [title, "先祖暗金胸甲", "900 物品强度", "鼠标右键"]
    assert observe_favorite(lines) == {
        "source": "raw_tts_title",
        "verification": "explicit_marker",
        "value": True,
        "text": title,
    }
    assert lines[0] == title


@pytest.mark.parametrize(
    "lines",
    [
        [],
        ["李奥瑞克的王冠", "先祖暗金头盔", "900 物品强度", "鼠标右键"],
        ["地狱火炬", "先祖神话神符", "900 物品强度", "鼠标右键"],
        ["[收藏物品]."],
        ["[收藏物品] 谜团"],
        ["[标记为垃圾]. 谜团"],
        ["[收藏物品]. [标记为垃圾]. 谜团"],
        ["[FAVORITED ITEM]. [MARKED AS JUNK]. Unknown item"],
        ["[FAVORITED ITEM]. [FAVORITED ITEM]. Unknown item"],
        ["未标记物品", "先祖暗金头盔", "[收藏物品]. 另一物品", "鼠标右键"],
    ],
)
def test_missing_ambiguous_or_other_title_favorite_evidence_remains_unknown(lines) -> None:
    assert observe_favorite(lines) is None
