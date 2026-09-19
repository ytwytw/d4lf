import logging
import typing
from types import SimpleNamespace

import pytest

if typing.TYPE_CHECKING:
    from pytest_mock import MockerFixture

from src.game_data import ItemRarity, ItemType
from src.item import Affix, AffixType, FilterResult, Item
from src.loot import filter as _filter
from src.loot.filter import check_items
from src.settings import ItemRefreshType


def test_force_without_filter_only_refreshes_item_status(monkeypatch, mocker: MockerFixture) -> None:
    inventory = mocker.Mock()
    inventory.get_item_slots.return_value = ([], [])
    reset = mocker.Mock()
    monkeypatch.setattr(_filter, "reset_item_status", reset)

    check_items(inventory, ItemRefreshType.force_without_filter)

    reset.assert_called_once_with([], inventory)
    inventory.hover_item_with_delay.assert_not_called()


def test_skipped_items_trigger_no_actions_but_still_check_advanced_tooltips(
    monkeypatch, mocker: MockerFixture, caplog
) -> None:
    inventory = mocker.Mock()
    slots = [SimpleNamespace(is_junk=False, is_fav=False) for _ in range(3)]
    inventory.get_item_slots.return_value = (slots, [])
    inventory.menu_name = "inventory"
    item = Item(item_type=ItemType.Helm, power=900, affixes=[Affix(name="armor", type=AffixType.greater)])
    monkeypatch.setattr(_filter.src.perception, "read_latest_item", lambda **_kwargs: item)
    monkeypatch.setattr(_filter, "capture", lambda: object())
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _item: False)
    monkeypatch.setattr(
        _filter, "Filter", lambda: SimpleNamespace(should_keep=lambda _item: FilterResult(False, [], True))
    )
    actions = [
        mocker.patch.object(_filter, name) for name in ("mark_as_favorite", "mark_as_junk", "drop_item_from_inventory")
    ]

    with caplog.at_level(logging.WARNING, logger=_filter.LOGGER.name):
        check_items(inventory, ItemRefreshType.no_refresh)

    for action in actions:
        action.assert_not_called()
    assert "3 out of 3 non-junk rarity items checked had all greater affixes" in caplog.text


def test_mythic_items_are_skipped_when_filter_category_is_disabled(monkeypatch, mocker: MockerFixture) -> None:
    inventory = mocker.Mock()
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False)], [])
    inventory.menu_name = "inventory"
    item = Item(item_type=ItemType.Helm, power=900, rarity=ItemRarity.Mythic)
    settings = SimpleNamespace(
        general=SimpleNamespace(
            filter_equipment=False,
            mark_as_favorite=True,
            do_not_junk_ancestral_legendaries=False,
            auto_use_temper_manuals=False,
        )
    )
    monkeypatch.setattr(_filter, "get_settings", lambda: settings)
    monkeypatch.setattr(_filter.src.perception, "read_latest_item", lambda **_kwargs: item)
    monkeypatch.setattr(_filter, "capture", lambda: object())
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _item: False)
    monkeypatch.setattr(
        _filter, "Filter", lambda: SimpleNamespace(should_keep=lambda _item: FilterResult(False, [], skipped=True))
    )
    favorite = mocker.patch.object(_filter, "mark_as_favorite")

    check_items(inventory, ItemRefreshType.no_refresh)

    favorite.assert_not_called()


@pytest.mark.parametrize("parse_error", [False, True])
def test_stale_or_invalid_item_is_bounded_and_never_mutated(monkeypatch, mocker, parse_error) -> None:
    inventory = mocker.Mock(menu_name="inventory")
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False)], [])
    reader = mocker.Mock(side_effect=ValueError("unknown translation") if parse_error else None, return_value=None)
    monkeypatch.setattr(_filter.src.perception, "latest_item_sequence", lambda: 12)
    monkeypatch.setattr(_filter.src.perception, "read_latest_item", reader)
    monkeypatch.setattr(_filter, "capture", lambda: None)
    monkeypatch.setattr(_filter.time, "sleep", lambda _: None)
    mocker.patch.object(_filter, "capture_latest_failure")
    evaluator = mocker.patch.object(_filter, "Filter")
    actions = [
        mocker.patch.object(_filter, name)
        for name in ("mark_as_favorite", "mark_as_junk", "drop_item_from_inventory", "reset_item_status")
    ]

    check_items(inventory, ItemRefreshType.no_refresh)

    assert reader.call_count == (1 if parse_error else 10)
    assert all(call.kwargs == {"after_sequence": 12} for call in reader.call_args_list)
    evaluator.assert_not_called()
    for action in actions:
        action.assert_not_called()


def test_delayed_item_uses_snapshot_taken_before_hover(monkeypatch, mocker) -> None:
    sequence = [12]
    inventory = mocker.Mock(menu_name="inventory")
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False)], [])
    inventory.hover_item_with_delay.side_effect = lambda _: sequence.__setitem__(0, 13)
    parsed = Item()
    reader = mocker.Mock(side_effect=[None, parsed])
    evaluator = mocker.Mock(return_value=FilterResult(False, [], skipped=True))
    monkeypatch.setattr(_filter.src.perception, "latest_item_sequence", lambda: sequence[0])
    monkeypatch.setattr(_filter.src.perception, "read_latest_item", reader)
    monkeypatch.setattr(_filter, "capture", lambda: None)
    monkeypatch.setattr(_filter.time, "sleep", lambda _: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _: False)
    monkeypatch.setattr(_filter, "Filter", lambda: SimpleNamespace(should_keep=evaluator))

    check_items(inventory, ItemRefreshType.no_refresh)

    assert reader.call_count == 2
    assert all(call.kwargs == {"after_sequence": 12} for call in reader.call_args_list)
    evaluator.assert_called_once_with(parsed)
