from src.settings.localization import category_group_title, category_label, field_description, field_title, option_label
from src.settings.models import LanguageType, SettingsCategory


def test_setting_helpers_use_stable_ids_and_requested_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.settings.localization.translate", lambda message_id, default=None: f"{message_id}|{default}"
    )

    assert category_label(SettingsCategory.UI).startswith("settings.category.ui|")
    assert category_group_title(SettingsCategory.HOTKEYS) == "settings.group.hotkeys|None"
    assert field_title("general", "language", "Language") == "settings.field.general.language.title|Language"
    assert field_description("general", "language", "Description") == (
        "settings.field.general.language.description|Description"
    )
    assert option_label(LanguageType.ZH_CN) == "settings.option.LanguageType.zhCN|zhCN"
