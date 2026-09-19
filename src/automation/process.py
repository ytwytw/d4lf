import ctypes
import logging
import os
from typing import TYPE_CHECKING

from src.automation.window.core import get_window_spec_id

if TYPE_CHECKING:
    import threading

    from src.automation.window.backend import WindowSpecLike

LOGGER = logging.getLogger(__name__)


def kill_thread(thread: threading.Thread) -> None:
    thread_id = thread.ident
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
    if res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
        LOGGER.error("Exception raise failure")


def safe_exit(error_code: int = 0) -> None:
    """Emergency-stop this instance and its threads, never unrelated Python processes."""
    os._exit(error_code)


def set_process_name(name: str, window_spec: WindowSpecLike) -> None:
    try:
        hwnd = get_window_spec_id(window_spec)
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.SetConsoleTitleW(hwnd, name)
    except AttributeError, OSError:
        LOGGER.exception("Failed to set process name")
