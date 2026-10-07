from pathlib import Path

import src.logger
import src.settings.errors
from src.settings.errors import SettingsLoadError


def test_settings_load_error_preserves_paths_and_original_exception() -> None:
    config_path = Path("params.ini")
    original = ValueError("invalid value")

    error = SettingsLoadError(config_path, original)

    assert error.config_path == config_path
    assert error.original is original
    assert str(config_path) in str(error)
    assert error.log_path.name == "logs"


def test_default_log_path_is_the_logger_directory() -> None:
    assert SettingsLoadError(Path("params.ini"), ValueError("bad")).log_path == src.logger.LOG_DIR


def test_frozen_log_path_points_beside_the_exe_not_into_the_unpacked_bundle(monkeypatch, tmp_path) -> None:
    install_dir = tmp_path / "D4LF install"
    bundle_module = tmp_path / "_MEI12345" / "src" / "settings" / "errors.pyc"
    monkeypatch.setattr(src.settings.errors, "__file__", str(bundle_module))
    monkeypatch.setattr(src.settings.errors, "BASE_DIR", install_dir)

    error = SettingsLoadError(Path("params.ini"), ValueError("bad"))

    assert error.log_path == install_dir / "logs"
    assert not error.log_path.is_relative_to(tmp_path / "_MEI12345")
