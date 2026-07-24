from types import SimpleNamespace

from src.gui import i18n
from src.item.data.affix import Affix
from src.item.filter import MatchedFilter, OverlayMatchName
from src.scripts import overlay_text as overlay_text_module
from src.scripts import vision_mode_fast
from src.scripts.overlay_text import display_profile_name, overlay_text


def test_overlay_messages_follow_the_active_language_without_renaming_user_profiles(monkeypatch) -> None:
    active_locale = {"value": i18n.EN_US}
    monkeypatch.setattr(i18n, "current_locale", lambda: active_locale["value"])

    assert overlay_text("Mythics always kept") == "Mythics always kept"
    assert display_profile_name("firewall.AspectUpgrades") == "firewall.AspectUpgrades"
    assert display_profile_name("My custom profile") == "My custom profile"

    active_locale["value"] = i18n.ZH_CN

    assert overlay_text("Mythics always kept") == "神话暗金始终保留"
    assert overlay_text("Codex Upgrade") == "力量法典升级"
    assert display_profile_name("firewall.AspectUpgrades") == "firewall.威能升级"
    assert display_profile_name("My custom profile") == "My custom profile"


def test_fast_overlay_localizes_match_reasons_and_affix_labels(monkeypatch) -> None:
    active_locale = {"value": i18n.ZH_CN}
    monkeypatch.setattr(i18n, "current_locale", lambda: active_locale["value"])
    monkeypatch.setattr(
        vision_mode_fast,
        "display_affix_name",
        lambda canonical: "最大闪避次数" if canonical == "maximum_evade_charges" else canonical,
    )
    match = MatchedFilter(
        profile="Mythics always kept",
        matched_affixes=[Affix(name="maximum_evade_charges")],
        aspect_match=True,
        set_match=True,
    )

    assert vision_mode_fast.create_match_text([match]) == ["神话暗金始终保留\n  - 最大闪避次数\n  - 威能\n  - 套装"]

    active_locale["value"] = i18n.EN_US

    assert overlay_text("Mythics always kept") == "Mythics always kept"


def test_generated_match_names_localize_only_builtin_segments(monkeypatch) -> None:
    active_locale = {"value": i18n.EN_US}
    monkeypatch.setattr(i18n, "current_locale", lambda: active_locale["value"])
    monkeypatch.setattr(
        overlay_text_module,
        "Dataloader",
        lambda: SimpleNamespace(aspect_unique_dict={"ring_of_starless_skies": {"display_name": "无星夜空之戒"}}),
    )

    section_match = OverlayMatchName.for_section("My.Charms.Profile", "Charms", "My.Seals.Rule")
    unique_match = OverlayMatchName.for_unique("My.Charms.Profile", "ring_of_starless_skies")

    assert display_profile_name(section_match) == "My.Charms.Profile.Charms.My.Seals.Rule"
    assert display_profile_name(unique_match) == "My.Charms.Profile.ring_of_starless_skies"
    assert display_profile_name("My.Charms.Profile.ring_of_starless_skies") == (
        "My.Charms.Profile.ring_of_starless_skies"
    )

    active_locale["value"] = i18n.ZH_CN

    assert display_profile_name(section_match) == "My.Charms.Profile.护身符.My.Seals.Rule"
    assert display_profile_name(unique_match) == "My.Charms.Profile.无星夜空之戒"
    assert display_profile_name("My.Charms.Profile.ring_of_starless_skies") == (
        "My.Charms.Profile.ring_of_starless_skies"
    )
