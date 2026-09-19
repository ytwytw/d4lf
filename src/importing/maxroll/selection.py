"""Resolve planner selections without substituting a different or hidden build."""

from typing import TYPE_CHECKING

from src.importing.maxroll.planner import MaxrollError, _resolve_visible_profile_index

if TYPE_CHECKING:
    from src.importing.contracts import ImportRequest
    from src.type_aliases import JsonObject


def select_profiles(
    profiles: list[JsonObject], request: ImportRequest, build_id: int, build_id_is_visible_position: bool
) -> list[tuple[int, JsonObject]]:
    visible = [(index, profile) for index, profile in enumerate(profiles) if not profile.get("hidden")]
    if not visible:
        message = "The Maxroll planner has no visible variants to import."
        raise MaxrollError(message)
    selection = request.variant_selection
    if selection is not None:
        available_ids = {str(index) for index, _ in visible}
        if not selection.ids or any(profile_id not in available_ids for profile_id in selection.ids):
            message = "The selected Maxroll variant is missing or hidden. Choose a current visible variant."
            raise MaxrollError(message)
        selected = [(index, profile) for index, profile in visible if str(index) in selection]
        if not request.options.multi_build and len(selected) != 1:
            message = "Choose exactly one visible Maxroll variant or enable multi-build import."
            raise MaxrollError(message)
        return selected
    if request.options.multi_build:
        return visible
    if build_id_is_visible_position:
        build_id = _resolve_visible_profile_index(profiles, build_id)
    if not 0 <= build_id < len(profiles) or profiles[build_id].get("hidden"):
        message = "The active Maxroll profile is missing or hidden. Choose a current visible variant."
        raise MaxrollError(message)
    return [(build_id, profiles[build_id])]
