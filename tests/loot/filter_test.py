"""Loot filter: inventory actions, degraded profile safety, fresh speech and unresolved names."""

import logging
import typing
from types import SimpleNamespace

import pytest

if typing.TYPE_CHECKING:
    from pytest_mock import MockerFixture

from src.game_data import ItemRarity, ItemType
from src.item import Affix, AffixType, FilterResult, Item
from src.item.filter import Filter
from src.loot import filter as _filter
from src.loot.filter import check_items
from src.perception import ItemTraceSnapshot, parse_item_text
from src.settings import ItemRefreshType
from tests.perception.parser.aspects_test import _tooltip as aspect_tooltip
from tests.perception.parser.tributes_test import _tooltip as tribute_tooltip


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
    monkeypatch.setattr(_filter, "read_fresh_item", lambda *_args: item)
    monkeypatch.setattr(_filter, "capture", lambda: object())
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _item: False)
    monkeypatch.setattr(
        _filter,
        "Filter",
        lambda: SimpleNamespace(should_keep=lambda _item: FilterResult(False, [], True), load_failures=()),
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
    monkeypatch.setattr(_filter, "read_fresh_item", lambda *_args: item)
    monkeypatch.setattr(_filter, "capture", lambda: object())
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _item: False)
    monkeypatch.setattr(
        _filter,
        "Filter",
        lambda: SimpleNamespace(should_keep=lambda _item: FilterResult(False, [], skipped=True), load_failures=()),
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
    monkeypatch.setattr(_filter.src.perception, "latest_raw_sequence", lambda: 40)
    monkeypatch.setattr(_filter, "read_fresh_item", reader)
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
    assert all(call.args == (12, 40) for call in reader.call_args_list)
    evaluator.assert_not_called()
    for action in actions:
        action.assert_not_called()


def test_delayed_item_uses_snapshot_taken_before_hover(monkeypatch, mocker) -> None:
    sequence = [12, 40]
    inventory = mocker.Mock(menu_name="inventory")
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False)], [])
    inventory.hover_item_with_delay.side_effect = lambda _: sequence.__setitem__(slice(None), [13, 45])
    parsed = Item()
    reader = mocker.Mock(side_effect=[None, parsed])
    evaluator = mocker.Mock(return_value=FilterResult(False, [], skipped=True))
    monkeypatch.setattr(_filter.src.perception, "latest_item_sequence", lambda: sequence[0])
    monkeypatch.setattr(_filter.src.perception, "latest_raw_sequence", lambda: sequence[1])
    monkeypatch.setattr(_filter, "read_fresh_item", reader)
    monkeypatch.setattr(_filter, "capture", lambda: None)
    monkeypatch.setattr(_filter.time, "sleep", lambda _: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _: False)
    monkeypatch.setattr(_filter, "Filter", lambda: SimpleNamespace(should_keep=evaluator, load_failures=()))

    check_items(inventory, ItemRefreshType.no_refresh)

    assert reader.call_count == 2
    assert all(call.args == (12, 40) for call in reader.call_args_list)
    evaluator.assert_called_once_with(parsed)


GOOD = "Affixes:\n- Ring:\n    itemType: [ring]\n    affixPool:\n    - count:\n      - {name: strength}\n"
RING = Item(item_type=ItemType.Ring, rarity=ItemRarity.Rare, power=800, affixes=[Affix(name="strength")])
BOOTS = Item(item_type=ItemType.Boots, rarity=ItemRarity.Rare, power=800, affixes=[Affix(name="strength")])
MYTHIC = Item(item_type=ItemType.Helm, rarity=ItemRarity.Mythic, power=800)


def _run(mocker, monkeypatch, items, refresh=ItemRefreshType.no_refresh, action="junk"):
    inventory = mocker.Mock(menu_name="inventory")
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False) for _ in items], [])
    queue = list(items)
    sequence = [0]

    def hover(_slot):
        sequence[0] += 1

    inventory.hover_item_with_delay.side_effect = hover
    monkeypatch.setattr(_filter.src.perception, "latest_item_sequence", lambda: sequence[0])
    monkeypatch.setattr(_filter, "read_fresh_item", lambda *_args: queue.pop(0))
    names = ("mark_as_junk", "mark_as_favorite", "drop_item_from_inventory", "reset_item_status")
    actions = {name: mocker.patch.object(_filter, name) for name in names}
    _filter.check_items(inventory, refresh, no_match_action=action)
    return actions


@pytest.mark.parametrize("action", ["junk", "drop"])
def test_one_broken_profile_blocks_negative_actions_but_keeps_positive_matches(profiles, mocker, monkeypatch, action):
    profiles(good=GOOD, broken="Affixes: [\n")
    actions = _run(mocker, monkeypatch, [RING, BOOTS], action=action)
    actions["mark_as_favorite"].assert_called_once()
    actions["mark_as_junk"].assert_not_called()
    actions["drop_item_from_inventory"].assert_not_called()
    assert Filter().load_failures == ("broken",)


def test_all_profiles_failed_still_takes_no_negative_action(profiles, mocker, monkeypatch):
    profiles(first="[invalid", second="Affixes: [\n")
    actions = _run(mocker, monkeypatch, [BOOTS, MYTHIC], action="drop")
    actions["mark_as_junk"].assert_not_called()
    actions["drop_item_from_inventory"].assert_not_called()
    actions["mark_as_favorite"].assert_called_once()  # mythics are still protected


def test_force_refresh_keeps_existing_marks_while_degraded(profiles, mocker, monkeypatch, caplog):
    profiles(good=GOOD, broken="[invalid")
    with caplog.at_level(logging.WARNING, logger=_filter.LOGGER.name):
        actions = _run(mocker, monkeypatch, [BOOTS], refresh=ItemRefreshType.force_with_filter)
    actions["reset_item_status"].assert_not_called()
    actions["mark_as_junk"].assert_not_called()
    assert "Keeping existing junk and favorite marks" in caplog.text


def test_healthy_profiles_keep_existing_behavior(profiles, mocker, monkeypatch):
    profiles(good=GOOD)
    actions = _run(mocker, monkeypatch, [RING, BOOTS], refresh=ItemRefreshType.force_with_filter)
    actions["reset_item_status"].assert_called_once()
    actions["mark_as_favorite"].assert_called_once()
    actions["mark_as_junk"].assert_called_once()


@pytest.mark.parametrize("recovery", ["restore", "disable"])
@pytest.mark.parametrize("failure", ["missing", "invalid"])
def test_skipped_profile_stays_protective_across_refreshes_until_restored_or_disabled(
    profiles, mocker, monkeypatch, caplog, tmp_path, failure, recovery
):
    profiles(good=GOOD, broken="[invalid")
    if failure == "missing":
        (tmp_path / "profiles" / "broken.yaml").unlink()
    runs = [(ItemRefreshType.no_refresh, "junk"), (ItemRefreshType.no_refresh, "drop")]
    with caplog.at_level(logging.WARNING, logger=_filter.LOGGER.name):
        for refresh, action in [*runs, (ItemRefreshType.force_with_filter, "junk")] * 3:
            actions = _run(mocker, monkeypatch, [BOOTS], refresh=refresh, action=action)
            for name in ("mark_as_junk", "drop_item_from_inventory", "reset_item_status"):
                actions[name].assert_not_called()
    assert caplog.text.count("Enabled profiles failed to load (broken)") == 1
    assert "在 Profile 面板中停用该 Profile" in caplog.text
    profiles.settings.save_value.assert_not_called()  # protection is never withdrawn silently
    if recovery == "restore":
        (tmp_path / "profiles" / "broken.yaml").write_text(GOOD + "# restored\n", encoding="utf-8")
    else:
        profiles.settings.general.profiles = ["good"]  # the user explicitly turns it off
    actions = _run(mocker, monkeypatch, [BOOTS], action="drop")
    actions["drop_item_from_inventory"].assert_called_once()
    assert Filter().load_failures == ()


def _snapshot(sequence: int, raw_start: int, lines: tuple[str, ...] = ("ITEM",), truncated: bool = False):
    return ItemTraceSnapshot(sequence, lines, lines, raw_start + len(lines), 0.0, raw_start, truncated)


@pytest.mark.parametrize(
    ("snapshot", "fresh"),
    [
        (_snapshot(5, 30), False),  # nothing completed since the hover
        (_snapshot(6, 18), False),  # previous slot's speech that completed late
        (_snapshot(6, 31, truncated=True), False),  # framing overflow: incomplete text
        (_snapshot(6, 31), True),
    ],
)
def test_read_fresh_item_requires_new_complete_speech(monkeypatch, snapshot, fresh) -> None:
    parsed = Item(original_name="ITEM")
    parse = []
    monkeypatch.setattr(_filter.src.perception, "complete_item_snapshot", lambda: snapshot)
    monkeypatch.setattr(_filter.src.perception, "parse_item_text", lambda lines: parse.append(lines) or parsed)
    assert (_filter.read_fresh_item(5, 30) is parsed) is fresh
    assert parse == ([["ITEM"]] if fresh else [])


def test_late_previous_trace_is_not_applied_to_the_hovered_slot(monkeypatch, mocker) -> None:
    raw = [30]
    snapshots = iter([_snapshot(6, 18, ("PREVIOUS",)), _snapshot(7, 31, ("CURRENT",))])
    inventory = mocker.Mock(menu_name="inventory")
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False)], [])
    inventory.hover_item_with_delay.side_effect = lambda _slot: raw.__setitem__(0, 31)
    monkeypatch.setattr(_filter.src.perception, "latest_item_sequence", lambda: 5)
    monkeypatch.setattr(_filter.src.perception, "latest_raw_sequence", lambda: raw[0])
    monkeypatch.setattr(_filter.src.perception, "complete_item_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(_filter.src.perception, "parse_item_text", lambda lines: Item(original_name=lines[0]))
    monkeypatch.setattr(_filter, "capture", lambda: None)
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(_filter, "is_ignored_item", lambda _item: False)
    evaluator = mocker.Mock(return_value=FilterResult(False, [], skipped=True))
    monkeypatch.setattr(_filter, "Filter", lambda: SimpleNamespace(should_keep=evaluator, load_failures=()))

    _filter.check_items(inventory, ItemRefreshType.no_refresh)

    evaluator.assert_called_once()
    assert evaluator.call_args.args[0].original_name == "CURRENT"


UNRESOLVED_ASPECT = aspect_tooltip("未知或截断的恶毒效果")
UNRESOLVED_TRIBUTE = tribute_tooltip("未知或截断效果")


@pytest.mark.parametrize("trace", [UNRESOLVED_ASPECT, UNRESOLVED_TRIBUTE], ids=["恶毒", "巨人贡品"])
@pytest.mark.parametrize("action", ["junk", "drop"])
def test_unresolved_shared_name_takes_no_inventory_action(zh, monkeypatch, mocker, trace, action) -> None:
    with pytest.raises(ValueError, match="legendary aspect|tribute name"):
        parse_item_text(trace)
    inventory = mocker.Mock(menu_name="inventory")
    inventory.get_item_slots.return_value = ([SimpleNamespace(is_junk=False, is_fav=False)], [])
    snapshot = ItemTraceSnapshot(2, tuple(trace), tuple(trace), 10 + len(trace), 0.0, 10)
    monkeypatch.setattr(_filter.src.perception, "latest_item_sequence", lambda: 1)
    monkeypatch.setattr(_filter.src.perception, "latest_raw_sequence", lambda: 5)
    monkeypatch.setattr(_filter.src.perception, "complete_item_snapshot", lambda: snapshot)
    monkeypatch.setattr(_filter, "capture", lambda: None)
    monkeypatch.setattr(_filter.time, "sleep", lambda _seconds: None)
    failure = mocker.patch.object(_filter, "capture_latest_failure")
    item_filter = mocker.patch.object(_filter, "Filter")
    names = ("mark_as_junk", "mark_as_favorite", "drop_item_from_inventory", "reset_item_status")
    actions = [mocker.patch.object(_filter, name) for name in names]

    _filter.check_items(inventory, ItemRefreshType.no_refresh, no_match_action=action)

    failure.assert_called_once()
    item_filter.assert_not_called()
    for mock in actions:
        mock.assert_not_called()
