import pytest
from pydantic import ValidationError

from src.settings.models import CATEGORY_KEY, HIDE_FROM_GUI_KEY, LanguageType, SettingsCategory
from src.settings.models.general import GeneralModel


class TestGeneralModel:
    def test_language_supports_english_and_simplified_chinese(self) -> None:
        assert GeneralModel(language="enUS").language is LanguageType.EN_US
        assert GeneralModel(language="zhCN").language is LanguageType.ZH_CN

        with pytest.raises(ValidationError):
            GeneralModel(language="unsupported")

    def test_language_setting_is_visible_and_controls_interface_and_game_locale(self) -> None:
        metadata = GeneralModel.model_json_schema()["properties"]["language"]

        assert metadata["title"] == "Interface and Game Language"
        assert metadata[CATEGORY_KEY] == SettingsCategory.SYSTEM
        assert not metadata.get(HIDE_FROM_GUI_KEY)

    def test_profiles_empty_entries_are_removed(self) -> None:
        assert GeneralModel(profiles="alpha, , beta,   ,").profiles == ["alpha", "beta"]

    def test_check_chest_tabs_preserves_zero_based_integer_input(self) -> None:
        assert GeneralModel(check_chest_tabs=[0, 2]).check_chest_tabs == [0, 2]
        assert GeneralModel(check_chest_tabs=["1", "3"]).check_chest_tabs == [0, 2]

    @pytest.mark.parametrize("value", [[1.5], [None], [True], [{"tab": 1}]])
    def test_check_chest_tabs_rejects_invalid_values(self, value: list[object]) -> None:
        with pytest.raises(ValidationError, match="list entries must be strings or integers"):
            GeneralModel.model_validate({"check_chest_tabs": value})

    def test_stash_tab_count_is_limited_to_six_or_seven(self) -> None:
        with pytest.raises(ValidationError, match="must be 6 or 7"):
            GeneralModel(max_stash_tabs=8)
