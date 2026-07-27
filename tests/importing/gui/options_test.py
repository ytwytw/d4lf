from src.importing import FilenamePart
from src.importing.gui.options import ImporterOptionsMixin


def test_filename_part_settings_use_stable_canonical_keys() -> None:
    assert ImporterOptionsMixin._filename_part_setting_key(FilenamePart.BUILD_TITLE) == ("filename_part_build_title")
