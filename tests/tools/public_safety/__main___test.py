import runpy

import pytest

from src.tools.public_safety import cli


def test_module_entrypoint_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "main", lambda: 7)

    with pytest.raises(SystemExit) as error:
        runpy.run_module("src.tools.public_safety.__main__", run_name="__main__")

    assert error.value.code == 7
