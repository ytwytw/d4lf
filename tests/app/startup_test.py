import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from src.app import startup
from src.app.startup import get_d4_local_prefs_file, prepare_runtime_directories


def test_runtime_directories_are_composed_from_settings(monkeypatch, tmp_path) -> None:
    class Settings:
        user_dir = tmp_path / "user"

    monkeypatch.setattr("src.app.startup.get_settings", lambda: Settings())

    prepare_runtime_directories()

    assert not (tmp_path / "logs" / "screenshots").exists()
    assert (tmp_path / "user" / "profiles").is_dir()


def test_local_prefs_returns_most_recent_candidate(monkeypatch, tmp_path) -> None:
    documents = tmp_path / "Documents" / "Diablo IV"
    documents.mkdir(parents=True)
    prefs = documents / "LocalPrefs.txt"
    prefs.write_text("prefs", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert get_d4_local_prefs_file() == prefs


def test_signature_check_uses_matching_engine_module_and_literal_path(monkeypatch, caplog) -> None:
    dll = Path("C:/Diablo's [test]/saapi64.dll")
    calls = []
    monkeypatch.setenv("SYSTEMROOT", "C:/Windows")
    monkeypatch.setenv("PSModulePath", "C:/foreign-powershell/Modules")

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="Valid\n", stderr="")

    monkeypatch.setattr(startup.subprocess, "run", run)
    with caplog.at_level(logging.DEBUG):
        startup._check_tts_dll_signature(dll)

    command, options = calls[0]
    assert Path(command[0]) == Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    assert command[1:4] == ["-NoProfile", "-NonInteractive", "-Command"]
    assert "Import-Module ($PSHOME +" in command[4]
    assert "-LiteralPath $env:D4LF_TTS_DLL_PATH" in command[4]
    assert str(dll) not in command[4]
    assert options["env"]["D4LF_TTS_DLL_PATH"] == str(dll)
    assert options["timeout"] == 15
    assert options["check"] is True
    assert "locally signed and valid" in caplog.text


@pytest.mark.parametrize("status", ["NotSigned", "HashMismatch", "NotTrusted", ""])
def test_signature_check_never_reports_untrusted_or_empty_status_as_valid(monkeypatch, caplog, status) -> None:
    monkeypatch.setenv("SYSTEMROOT", "C:/Windows")
    monkeypatch.setattr(
        startup.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout=status, stderr=""),
    )

    with caplog.at_level(logging.DEBUG):
        startup._check_tts_dll_signature(Path("C:/Diablo/saapi64.dll"))

    assert "must be locally signed" in caplog.text
    assert "run install_dll.cmd" in caplog.text
    assert "locally signed and valid" not in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("PowerShell missing"),
        subprocess.TimeoutExpired("powershell", timeout=15),
        subprocess.CalledProcessError(1, "powershell", stderr="Security module failed"),
    ],
)
def test_signature_check_failure_is_nonfatal_and_reports_unknown_trust(monkeypatch, caplog, error) -> None:
    monkeypatch.setenv("SYSTEMROOT", "C:/Windows")

    def run(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(startup.subprocess, "run", run)
    startup._check_tts_dll_signature(Path("C:/Diablo/saapi64.dll"))

    assert "trust status is unknown" in caplog.text
    assert "must be locally signed" not in caplog.text
    if isinstance(error, subprocess.CalledProcessError):
        assert "Security module failed" in caplog.text


def test_tts_diagnostics_skip_processes_that_exit_during_inspection(monkeypatch, caplog) -> None:
    class ExitedProcess:
        def name(self) -> str:
            raise psutil.NoSuchProcess(42)

    monkeypatch.setattr(startup.sys, "platform", "win32")
    monkeypatch.setattr(startup.psutil, "process_iter", lambda *_args: [ExitedProcess()])
    monkeypatch.setattr(
        startup, "get_settings", lambda: SimpleNamespace(advanced_options=SimpleNamespace(disable_tts_warning=True))
    )

    startup.check_for_proper_tts_configuration()

    assert "No process named Diablo IV.exe" in caplog.text
