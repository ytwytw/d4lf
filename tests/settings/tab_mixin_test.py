import os
import sys

import pytest

from src.settings.tab_mixin import ConfigTabMixin


def test_config_tab_mixin_exposes_setting_generation_operations() -> None:
    assert callable(ConfigTabMixin._filter_settings)
    assert callable(ConfigTabMixin._save_setting_value)


@pytest.mark.parametrize("frozen", [True, False])
def test_restart_keeps_resources_alive_after_parent_exit(mocker, monkeypatch, frozen) -> None:
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "argv", ["d4lf.py", "--debug"])
    monkeypatch.setenv("SSL_CERT_FILE", "custom-ca.pem")
    monkeypatch.delenv("PYINSTALLER_RESET_ENVIRONMENT", raising=False)
    environment_before = os.environ.copy()
    launch = mocker.patch("src.settings.tab_mixin.subprocess.Popen")
    application = mocker.Mock()
    mocker.patch("src.settings.tab_mixin.QCoreApplication.instance", return_value=application)

    ConfigTabMixin()._restart_application()

    launch.assert_called_once()
    assert launch.call_args.args[0] == [sys.executable, *(["--debug"] if frozen else sys.argv)]
    if frozen:
        assert launch.call_args.kwargs["env"] == {**environment_before, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    else:
        assert launch.call_args.kwargs.get("env") is None
    assert os.environ == environment_before
    application.quit.assert_called_once()


def test_failed_restart_keeps_current_application_open(mocker) -> None:
    mocker.patch("src.settings.tab_mixin.subprocess.Popen", side_effect=OSError("cannot start replacement"))
    dialog = mocker.patch("src.settings.tab_mixin.QMessageBox").return_value
    application = mocker.Mock()
    mocker.patch("src.settings.tab_mixin.QCoreApplication.instance", return_value=application)

    ConfigTabMixin()._restart_application()

    dialog.exec.assert_called_once()
    application.quit.assert_not_called()
