from types import SimpleNamespace

import pytest

from src.config.settings_models import AdvancedOptionsModel, CharModel, GeneralModel, ItemRefreshType
from src.item.data.item_type import ItemType
from src.item.data.rarity import ItemRarity
from src.scripts import common, loot_filter_tts


@pytest.fixture
def zhcn_interaction(mocker):
    config = SimpleNamespace(
        advanced_options=AdvancedOptionsModel(vision_mode_only=False),
        char=CharModel(),
        general=GeneralModel(language="zhCN"),
    )
    mocker.patch.object(common, "IniConfigLoader", return_value=config)
    mocker.patch.object(loot_filter_tts, "IniConfigLoader", return_value=config)
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=False)
    mocker.patch.object(common, "is_window_foreground", return_value=True)
    keyboard = mocker.patch.object(common, "hotkeys")
    mouse = mocker.patch.object(common, "Mouse")
    mocker.patch.object(common.time, "sleep")
    mocker.patch.object(loot_filter_tts.time, "sleep")
    mocker.patch.object(loot_filter_tts, "Cam")
    mocker.patch.object(loot_filter_tts, "capture_failure")
    mocker.patch.object(loot_filter_tts.src.tts, "get_item_trace_snapshot", return_value=([], []))
    return SimpleNamespace(config=config, keyboard=keyboard, mouse=mouse)


def _item() -> SimpleNamespace:
    return SimpleNamespace(affixes=[], is_ancestral=False, item_type=ItemType.Helm, rarity=ItemRarity.Rare)


def _inventory(mocker, *slots):
    inventory = mocker.Mock()
    inventory.menu_name = "Inventory"
    inventory.get_item_slots.return_value = (list(slots), [])
    return inventory


def _slot(*, favorite: bool = False, junk: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_fav=favorite, is_junk=junk)


def _mock_filter_pipeline(mocker, result):
    mocker.patch.object(loot_filter_tts, "is_ignored_item", return_value=False)
    read_descr = mocker.patch.object(loot_filter_tts.src.item.descr.read_descr_tts, "read_descr", return_value=_item())
    filter_instance = mocker.patch.object(loot_filter_tts, "Filter").return_value
    filter_instance.should_keep.return_value = result
    actions = SimpleNamespace(
        favorite=mocker.patch.object(loot_filter_tts, "mark_as_favorite"),
        junk=mocker.patch.object(loot_filter_tts, "mark_as_junk"),
        drop=mocker.patch.object(loot_filter_tts, "drop_item_from_inventory"),
        reset=mocker.patch.object(loot_filter_tts, "reset_item_status"),
        use=mocker.patch.object(loot_filter_tts, "use_item_from_inventory"),
    )
    return read_descr, actions


def _assert_no_real_input(interaction) -> None:
    assert interaction.keyboard.mock_calls == []
    assert interaction.mouse.mock_calls == []


def test_zhcn_unmatched_item_is_marked_as_junk_offline(mocker, zhcn_interaction) -> None:
    inventory = _inventory(mocker, _slot())
    _, actions = _mock_filter_pipeline(mocker, SimpleNamespace(keep=False, matched=[]))

    loot_filter_tts.check_items(inventory, ItemRefreshType.no_refresh)

    actions.junk.assert_called_once_with()
    actions.favorite.assert_not_called()
    actions.drop.assert_not_called()
    _assert_no_real_input(zhcn_interaction)


def test_zhcn_unmatched_item_reaches_mocked_junk_hotkey(mocker, zhcn_interaction) -> None:
    inventory = _inventory(mocker, _slot())
    mocker.patch.object(loot_filter_tts, "is_ignored_item", return_value=False)
    mocker.patch.object(loot_filter_tts.src.item.descr.read_descr_tts, "read_descr", return_value=_item())
    filter_instance = mocker.patch.object(loot_filter_tts, "Filter").return_value
    filter_instance.should_keep.return_value = SimpleNamespace(keep=False, matched=[])
    mocker.patch.object(loot_filter_tts, "mark_as_favorite")
    mocker.patch.object(loot_filter_tts, "drop_item_from_inventory")
    mocker.patch.object(loot_filter_tts, "reset_item_status")
    mocker.patch.object(loot_filter_tts, "use_item_from_inventory")

    loot_filter_tts.check_items(inventory, ItemRefreshType.no_refresh)

    zhcn_interaction.keyboard.send.assert_called_once_with("space")
    assert zhcn_interaction.mouse.mock_calls == []


def test_zhcn_matching_item_is_favorited_offline(mocker, zhcn_interaction) -> None:
    inventory = _inventory(mocker, _slot())
    match = SimpleNamespace(profile="build.helm", matched_affixes=[object()], aspect_match=False)
    _, actions = _mock_filter_pipeline(mocker, SimpleNamespace(keep=True, matched=[match]))

    loot_filter_tts.check_items(inventory, ItemRefreshType.no_refresh)

    actions.favorite.assert_called_once_with()
    actions.junk.assert_not_called()
    actions.drop.assert_not_called()
    _assert_no_real_input(zhcn_interaction)


def test_zhcn_existing_favorite_and_junk_items_are_not_touched(mocker, zhcn_interaction) -> None:
    inventory = _inventory(mocker, _slot(favorite=True), _slot(junk=True))
    read_descr, actions = _mock_filter_pipeline(mocker, SimpleNamespace(keep=False, matched=[]))

    loot_filter_tts.check_items(inventory, ItemRefreshType.no_refresh)

    read_descr.assert_not_called()
    actions.favorite.assert_not_called()
    actions.junk.assert_not_called()
    actions.drop.assert_not_called()
    actions.reset.assert_not_called()
    actions.use.assert_not_called()
    _assert_no_real_input(zhcn_interaction)


@pytest.mark.parametrize(("stash_is_open", "expected_action"), [(False, "drop"), (True, "junk")])
def test_zhcn_drop_mode_never_drops_from_stash(
    mocker, zhcn_interaction, stash_is_open: bool, expected_action: str
) -> None:
    inventory = _inventory(mocker, _slot())
    _, actions = _mock_filter_pipeline(mocker, SimpleNamespace(keep=False, matched=[]))

    loot_filter_tts.check_items(
        inventory, ItemRefreshType.no_refresh, stash_is_open=stash_is_open, no_match_action="drop"
    )

    getattr(actions, expected_action).assert_called_once_with()
    other_action = "junk" if expected_action == "drop" else "drop"
    getattr(actions, other_action).assert_not_called()
    actions.favorite.assert_not_called()
    _assert_no_real_input(zhcn_interaction)


def test_zhcn_force_refresh_resets_status_before_filtering(mocker, zhcn_interaction) -> None:
    marked = _slot(junk=True)
    refreshed = _slot()
    inventory = mocker.Mock()
    inventory.menu_name = "Inventory"
    inventory.get_item_slots.side_effect = [([marked], []), ([refreshed], [])]
    _, actions = _mock_filter_pipeline(mocker, SimpleNamespace(keep=False, matched=[]))

    loot_filter_tts.check_items(inventory, ItemRefreshType.force_with_filter)

    actions.reset.assert_called_once_with([marked], inventory)
    actions.junk.assert_called_once_with()
    actions.favorite.assert_not_called()
    _assert_no_real_input(zhcn_interaction)


def test_zhcn_diagnostic_capture_blocks_filter_before_inventory_scan(mocker, zhcn_interaction) -> None:
    inventory = _inventory(mocker, _slot())
    mocker.patch.object(common, "is_diagnostic_capture_active", return_value=True)

    loot_filter_tts.check_items(inventory, ItemRefreshType.no_refresh)

    inventory.get_item_slots.assert_not_called()
    _assert_no_real_input(zhcn_interaction)
