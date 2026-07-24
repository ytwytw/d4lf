import sys
import threading
from typing import TYPE_CHECKING

import pywintypes
import win32file
import win32pipe
import win32security

if TYPE_CHECKING:
    import logging
    import queue
    from collections.abc import Callable


def _require_message_size(value: object) -> int:
    if not isinstance(value, int):
        message = "Named pipe returned an invalid message size"
        raise TypeError(message)
    return value


def _require_message_bytes(value: object) -> bytes:
    if not isinstance(value, bytes):
        message = "Named pipe returned a non-byte message"
        raise TypeError(message)
    return value


_PIPE_DISCONNECTED_ERRORS = frozenset({109, 232, 233})
_PIPE_ALREADY_CONNECTED = 535


def _pipe_error_code(error: BaseException) -> int | None:
    if error.args and isinstance(error.args[0], int):
        return error.args[0]
    return None


def _close_pipe(handle: int, logger: logging.Logger) -> None:
    try:
        win32pipe.DisconnectNamedPipe(handle)
    except pywintypes.error as error:
        if _pipe_error_code(error) not in _PIPE_DISCONNECTED_ERRORS:
            logger.debug("Could not disconnect the TTS pipe cleanly", exc_info=True)
    try:
        win32file.CloseHandle(handle)
    except pywintypes.error:
        logger.debug("Could not close the TTS pipe handle cleanly", exc_info=True)


def _create_named_pipe() -> int:
    return win32pipe.CreateNamedPipe(
        r"\\.\pipe\d4lf",
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
        1,
        65536,
        65536,
        0,
        win32security.SECURITY_ATTRIBUTES(),
    )


def create_pipe(logger: logging.Logger) -> int:
    try:
        return _create_named_pipe()
    except pywintypes.error as e:
        if e.args[0] == 231:  # ERROR_PIPE_BUSY
            logger.error("")
            logger.error("=" * 80)
            logger.error("D4LF IS ALREADY RUNNING")
            logger.error("=" * 80)
            logger.error("")
            logger.error("You already have D4LF running in another window.")
            logger.error("Please close your windows and re-launch.")
            logger.error("")
            logger.error("=" * 80)
            sys.exit(1)
        raise


def read_pipe(
    create_pipe_fn: Callable[[], int],
    data_queue: queue.Queue[str],
    logger: logging.Logger,
    set_connected: Callable[[bool], None],
    decode_payload: Callable[[bytes], str],
    *,
    stop_event: threading.Event | None = None,
    reconnect_delay: float = 0.1,
) -> None:
    stop_event = stop_event or threading.Event()
    while not stop_event.is_set():
        handle: int | None = None
        was_connected = False
        try:
            handle = create_pipe_fn()
            logger.debug("Waiting for TTS client to connect")
            try:
                win32pipe.ConnectNamedPipe(handle, None)
            except pywintypes.error as error:
                if _pipe_error_code(error) != _PIPE_ALREADY_CONNECTED:
                    raise
            logger.info("TTS client connected")
            set_connected(True)
            was_connected = True

            while not stop_event.is_set():
                win32file.ReadFile(handle, 0)
                _, _, message_size = win32pipe.PeekNamedPipe(handle, 0)
                message_size = _require_message_size(message_size)
                _, raw_data = win32file.ReadFile(handle, message_size)
                data = decode_payload(_require_message_bytes(raw_data))
                if not data:
                    continue
                if "DISCONNECTED" in data:
                    break
                data_queue.put(data)
        except pywintypes.error as error:
            if _pipe_error_code(error) not in _PIPE_DISCONNECTED_ERRORS:
                logger.exception("TTS pipe error; reconnecting")
        except UnicodeError:
            logger.exception("Could not decode TTS pipe data; reconnecting")
        finally:
            set_connected(False)
            if handle is not None:
                _close_pipe(handle, logger)
            if was_connected:
                logger.info("TTS client disconnected")

        if not stop_event.is_set():
            stop_event.wait(reconnect_delay)


def start_connection(
    start_find_item: Callable[[], None], start_read_pipe: Callable[[], None], logger: logging.Logger
) -> None:
    logger.info("Starting TTS listener. Hover over an item or button to perform the TTS connection.")
    threading.Thread(target=start_find_item, daemon=True).start()
    threading.Thread(target=start_read_pipe, daemon=True).start()
