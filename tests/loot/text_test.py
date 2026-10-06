from types import SimpleNamespace

import src.loot.text as text_module
from src.loot.text import affix_text, match_profile_text


def test_match_profile_translates_only_application_owned_labels(monkeypatch) -> None:
    monkeypatch.setattr(text_module, "translate", lambda message_id, _default=None: f"<{message_id}>")

    assert match_profile_text("Mythics always kept") == "<loot.reason.mythics_always_kept>"
    assert match_profile_text("My Build.AspectUpgrades") == "My Build.<loot.section.aspect_upgrades>"
    assert match_profile_text("Mythics always kept copy") == "Mythics always kept copy"


def test_affix_text_uses_active_locale_catalog_and_falls_back(monkeypatch) -> None:
    data = SimpleNamespace(
        affix_dict={"armor": "护甲"}, seal_affix_dict={"seal_damage": "印记伤害"}, charm_affix_dict={}
    )
    monkeypatch.setattr(text_module, "GameCatalog", lambda: data)

    assert affix_text("armor") == "护甲"
    assert affix_text("seal_damage") == "印记伤害"
    assert affix_text("unknown") == "unknown"
