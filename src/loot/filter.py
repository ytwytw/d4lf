import logging
import time
from typing import TYPE_CHECKING

import src.perception
from src import automation
from src.diagnostics import capture_latest_failure
from src.game_data import ItemRarity, ItemType, is_sigil
from src.item import ASPECT_UPGRADES_LABEL, AffixType
from src.item.filter import Filter
from src.loot.colors import drop_item_from_inventory, is_ignored_item, mark_as_favorite, mark_as_junk, reset_item_status
from src.perception import capture
from src.settings import ItemRefreshType, UnfilteredUniquesType, get_settings

if TYPE_CHECKING:
    from src.automation import Inventory
    from src.item import Item

LOGGER = logging.getLogger(__name__)
_DEGRADED_NOTICE: tuple[str, ...] = ()


def read_fresh_item(item_sequence: int, raw_sequence: int) -> Item | None:
    """Parse the newest complete trace only if its speech began after the hover, like the inventory reader.

    A trace that completes late for the previous slot is otherwise newer than this slot's baseline.
    """
    snapshot = src.perception.complete_item_snapshot()
    if snapshot.sequence <= item_sequence:
        return None
    if snapshot.raw_start_sequence <= raw_sequence or snapshot.truncated:
        LOGGER.debug("Ignoring item text that began before this hover or exceeded the framing limit.")
        return None
    return src.perception.parse_item_text(list(snapshot.normalized_lines))


def _skipped_profiles(item_filter: Filter) -> tuple[str, ...]:
    """Enabled profiles that failed to load; while any exist, negative decisions are incomplete."""
    global _DEGRADED_NOTICE
    skipped = tuple(item_filter.load_failures)
    if skipped and skipped != _DEGRADED_NOTICE:
        LOGGER.warning(
            "Enabled profiles failed to load (%s). Unmatched items are not marked as junk or dropped until they "
            "load; matching items can still be marked as favorites. Restore or fix the file, or turn the profile "
            "off in the Profiles panel. / 已启用的 Profile 无法加载（%s）。恢复加载前不会把未匹配物品标记为垃圾或丢弃，"
            "匹配的物品仍可收藏。请恢复或修复文件，或在 Profile 面板中停用该 Profile。",
            ", ".join(skipped),
            "、".join(skipped),
        )
    elif _DEGRADED_NOTICE and not skipped:
        LOGGER.warning(
            "All enabled profiles load again; unmatched items are handled normally. / 所有已启用的 Profile 已恢复加载，未匹配物品恢复正常处理。"
        )
    _DEGRADED_NOTICE = skipped
    return skipped


def check_items(
    inv: Inventory, force_refresh: ItemRefreshType, stash_is_open: bool = False, no_match_action: str = "junk"
) -> None:
    occupied, _ = inv.get_item_slots()

    def _handle_no_match(skipped_profiles: tuple[str, ...]) -> None:
        if skipped_profiles:
            # A skipped profile might have kept this item, so a negative result is not trustworthy.
            LOGGER.info(
                "Leaving unmatched item unmarked: enabled profiles failed to load. / 有 Profile 未加载，保留未匹配物品不标记。"
            )
        elif no_match_action == "drop" and not stash_is_open:
            drop_item_from_inventory()
        else:
            mark_as_junk()

    if force_refresh == ItemRefreshType.force_without_filter:
        reset_item_status(occupied, inv)
        return
    if force_refresh == ItemRefreshType.force_with_filter:
        refresh_filter = Filter()
        refresh_filter.ensure_current()
        if _skipped_profiles(refresh_filter):
            LOGGER.warning(
                "Keeping existing junk and favorite marks because enabled profiles failed to load. / "
                "有已启用的 Profile 无法加载，保留现有的垃圾和收藏标记。"
            )
        else:
            reset_item_status(occupied, inv)
            occupied, _ = inv.get_item_slots()

    num_fav = sum(1 for slot in occupied if slot.is_fav)
    num_junk = sum(1 for slot in occupied if slot.is_junk)
    LOGGER.info(f"Items: {len(occupied)} (favorite: {num_fav}, junk: {num_junk}) in {inv.menu_name}")
    # These are used to check if there's any signs that the user does not have Advanced Tooltip Comparison on
    num_of_items_with_all_ga = 0
    num_of_affixed_items_checked = 0
    start_checking_items = time.time()
    for item in occupied:
        if item.is_junk or item.is_fav:
            continue
        sequence_before_hover = src.perception.latest_item_sequence()
        raw_before_hover = src.perception.latest_raw_sequence()
        inv.hover_item_with_delay(item)
        time.sleep(0.1)
        img = capture()
        item_descr = None
        for retry_count in range(10):
            try:
                item_descr = read_fresh_item(sequence_before_hover, raw_before_hover)
                LOGGER.debug(f"Attempt {retry_count} to parse item based on TTS: {item_descr}")
            except Exception as error:
                capture_latest_failure(reason="loot-filter-item-parse", image=img, error=error)
                LOGGER.exception(f"Error in TTS read_descr. {src.perception.latest_item_lines()=}")
                break
            if item_descr is not None:
                break
            time.sleep(0.1)

        if item_descr is None:
            LOGGER.warning("Skipping inventory slot: no fresh, valid item text after hovering.")
            continue

        # Hardcoded filters
        if is_ignored_item(item_descr):
            if (
                not stash_is_open
                and item_descr.item_type == ItemType.TemperManual
                and get_settings().general.auto_use_temper_manuals
            ):
                automation.click_pointer("right")
            continue

        num_of_affixed_items_checked += 1
        if item_descr.affixes and all(affix.type == AffixType.greater for affix in item_descr.affixes):
            num_of_items_with_all_ga += 1

        item_filter = Filter()
        res = item_filter.should_keep(item_descr)
        skipped_profiles = _skipped_profiles(item_filter)
        if res.skipped:
            continue

        matched_any_affixes = len(res.matched) > 0 and len(res.matched[0].matched_affixes) > 0
        matched_profile_legendary_aspect = any(
            match.profile.endswith(f".{ASPECT_UPGRADES_LABEL}") for match in res.matched
        )

        # Uniques have special handling. They might be a keep but should actually be ignored
        if item_descr.rarity == ItemRarity.Unique and item_descr.item_type != ItemType.Tribute:
            if not res.keep:
                _handle_no_match(skipped_profiles)
            elif len(res.matched) == 1 and res.matched[0].profile.lower() == "cosmetics":
                LOGGER.info("Ignoring unique because it matches no filters and is a cosmetic upgrade.")
            elif any(match.aspect_match for match in res.matched) and get_settings().general.mark_as_favorite:
                # This means it was a legitimate match, not an ignore
                mark_as_favorite()
            elif get_settings().general.handle_uniques == UnfilteredUniquesType.favorite:
                mark_as_favorite()
        elif not res.keep:
            if get_settings().general.do_not_junk_ancestral_legendaries and item_descr.is_ancestral:
                LOGGER.info("Skipping marking as junk because it is an ancestral legendary.")
            else:
                _handle_no_match(skipped_profiles)
        elif (
            matched_any_affixes
            or matched_profile_legendary_aspect
            or item_descr.rarity == ItemRarity.Mythic
            or is_sigil(item_descr.item_type)
            or item_descr.item_type == ItemType.Tribute
        ) and get_settings().general.mark_as_favorite:
            mark_as_favorite()

    LOGGER.debug(f"Time to filter all items in stash/inventory tab: {time.time() - start_checking_items:.2f}s")

    # If more than 80% of the items had all greater affixes that means something is probably wrong
    if num_of_affixed_items_checked > 2 and (num_of_items_with_all_ga / num_of_affixed_items_checked > 0.8):
        LOGGER.warning(
            f"{num_of_items_with_all_ga} out of {num_of_affixed_items_checked} non-junk rarity items checked had all greater affixes. You are either exceptionally lucky or have not enabled Advanced Tooltip Information in Options > Gameplay"
        )
