"""Startup preparation and Windows runtime diagnostics."""

import logging
import os
import pathlib
import subprocess
import sys
from pathlib import Path

import psutil
from PyQt6.QtWidgets import QMessageBox, QWidget

from src.settings import SettingsLoadError, VisionModeType, get_settings

REPOSITORY_URL = "https://github.com/ytwytw/d4lf"
SETUP_INSTRUCTIONS_URL = f"{REPOSITORY_URL}/blob/main/README.md#安装"
LOGGER = logging.getLogger(__name__)


def _check_tts_dll_signature(tts_dll: Path) -> None:
    """Check trust without loading profiles or modules from another PowerShell edition."""
    powershell = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    environment = os.environ.copy()
    environment["D4LF_TTS_DLL_PATH"] = str(tts_dll)
    # PSModulePath can contain PowerShell 7 modules when launched from pwsh. Windows
    # PowerShell must load its own security module; incompatible type data prevents autoload.
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "Import-Module ($PSHOME + '\\Modules\\Microsoft.PowerShell.Security\\Microsoft.PowerShell.Security.psd1'); "
        "(Get-AuthenticodeSignature -LiteralPath $env:D4LF_TTS_DLL_PATH).Status"
    )
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        details = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else error
        LOGGER.warning("Unable to check saapi64.dll signature; trust status is unknown: %s", details)
        return
    status = result.stdout.strip()
    if status == "Valid":
        LOGGER.debug("%s is locally signed and valid.", tts_dll)
    else:
        LOGGER.error(
            "As of season 12, the saapi64.dll must be locally signed. Follow all instructions in %s "
            "to get the dll signed (specifically, run install_dll.cmd). It currently has a status of %s",
            SETUP_INSTRUCTIONS_URL,
            status or "Unknown",
        )


def show_settings_load_error(error: SettingsLoadError, parent: QWidget | None = None) -> None:
    """Show the startup settings failure without allowing the app to continue."""
    QMessageBox.critical(
        parent,
        "D4LF settings error",
        f"Could not load settings from:\n{error.config_path}\n\nDetails were written to:\n{error.log_path}",
    )


def prepare_runtime_directories() -> None:
    """Create the user-data and screenshot directories required at startup."""
    settings = get_settings()
    for directory in (settings.user_dir, settings.user_dir / "profiles"):
        Path(directory).mkdir(exist_ok=True, parents=True)


def check_for_proper_tts_configuration() -> None:
    """Log actionable diagnostics for the installed TTS DLL and game settings."""
    if sys.platform != "win32":
        LOGGER.debug("Skipping TTS configuration checks on non-Windows.")
        return

    d4_process_found = False
    tts_dll = None
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            if proc.name().lower() != "diablo iv.exe":
                continue
            d4_dir = Path(proc.exe()).parent
        except psutil.NoSuchProcess, psutil.AccessDenied:
            continue
        tts_dll = d4_dir / "saapi64.dll"
        if not tts_dll.exists():
            LOGGER.warning(
                f"TTS DLL was not found in {d4_dir}. Have you followed the instructions in {SETUP_INSTRUCTIONS_URL}?"
            )
        else:
            LOGGER.debug(f"TTS DLL found at {tts_dll}")
        d4_process_found = True
        break

    if tts_dll and tts_dll.exists():
        _check_tts_dll_signature(tts_dll)

    if not d4_process_found:
        LOGGER.warning(
            "No process named Diablo IV.exe was found and unable to automatically determine if TTS DLL is installed."
        )

    settings = get_settings()
    if settings.advanced_options.disable_tts_warning:
        LOGGER.debug("Disable TTS warning is enabled, skipping TTS local prefs check")
        return
    local_prefs = get_d4_local_prefs_file()
    if local_prefs is None:
        LOGGER.warning(
            "Unable to find a Diablo 4 local prefs file. Can't automatically check if TTS is configured properly in-game. "
            "If d4lf is working without issue for you, you can disable this warning by enabling 'disable_tts_warning' in the Advanced settings."
        )
        return

    prefs = local_prefs.read_text(encoding="utf-8")
    if 'UseScreenReader "1"' not in prefs:
        LOGGER.error(
            f"Use Screen Reader is not enabled in Accessibility Settings in D4. No items will be read. Read more about initial setup here: {SETUP_INSTRUCTIONS_URL}"
        )
    if 'UseThirdPartyReader "1"' not in prefs:
        LOGGER.error(
            f"3rd Party Screen Reader is not enabled in D4. No items will be read. Read more about initial setup here: {SETUP_INSTRUCTIONS_URL}"
        )
    if 'FontScale "2"' in prefs and settings.general.vision_mode_type == VisionModeType.highlight_matches:
        LOGGER.error(
            "A font scale set to Large is not supported when using the highlight matches vision mode. Change to medium or small in the graphics options, or use the fast vision mode."
        )


def get_d4_local_prefs_file() -> Path | None:
    """Return the most recently modified Diablo 4 preferences file."""
    candidates = [
        pathlib.Path.home() / "Documents" / "Diablo IV" / "LocalPrefs.txt",
        pathlib.Path.home() / "OneDrive" / "Documents" / "Diablo IV" / "LocalPrefs.txt",
        pathlib.Path.home() / "OneDrive" / "MyDocuments" / "Diablo IV" / "LocalPrefs.txt",
    ]
    existing = [file for file in candidates if file.exists()]
    most_recent: Path | None = None
    for file in existing:
        if most_recent is None or file.stat().st_mtime > most_recent.stat().st_mtime:
            most_recent = file
    return most_recent
