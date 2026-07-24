import logging
from threading import Event

from src import tts, tts_backend_windows


class PipeError(Exception):
    pass


def test_broken_tts_pipe_closes_each_handle_once_and_reconnects(monkeypatch, caplog) -> None:
    stop_event = Event()
    handles = iter(["first", "second"])
    created = []
    connected = []
    read = []
    disconnected = []
    closed = []

    def create_pipe():
        handle = next(handles)
        created.append(handle)
        return handle

    def connect(handle, _overlapped):
        connected.append(handle)

    def read_file(handle, _size):
        read.append(handle)
        raise PipeError(109, "ReadFile", "pipe ended")

    def disconnect(handle):
        disconnected.append(handle)

    def close(handle):
        closed.append(handle)
        if handle == "second":
            stop_event.set()

    monkeypatch.setattr(tts_backend_windows.pywintypes, "error", PipeError)
    monkeypatch.setattr(tts, "create_pipe", create_pipe)
    monkeypatch.setattr(tts_backend_windows.win32pipe, "ConnectNamedPipe", connect)
    monkeypatch.setattr(tts_backend_windows.win32pipe, "DisconnectNamedPipe", disconnect)
    monkeypatch.setattr(tts_backend_windows.win32file, "ReadFile", read_file)
    monkeypatch.setattr(tts_backend_windows.win32file, "CloseHandle", close)
    caplog.set_level(logging.ERROR, logger=tts.LOGGER.name)

    tts.read_pipe(stop_event=stop_event, reconnect_delay=0)

    assert created == ["first", "second"]
    assert connected == created
    assert read == created
    assert disconnected == created
    assert closed == created
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert tts.CONNECTED is False


def test_unexpected_tts_pipe_error_is_logged_once_before_reconnect(monkeypatch, caplog) -> None:
    stop_event = Event()

    monkeypatch.setattr(tts_backend_windows.pywintypes, "error", PipeError)
    monkeypatch.setattr(tts, "create_pipe", lambda: "handle")
    monkeypatch.setattr(tts_backend_windows.win32pipe, "ConnectNamedPipe", lambda _handle, _overlapped: None)
    monkeypatch.setattr(tts_backend_windows.win32pipe, "DisconnectNamedPipe", lambda _handle: None)

    def fail_read(_handle, _size):
        raise PipeError(123, "ReadFile", "unexpected")

    def close(_handle):
        stop_event.set()

    monkeypatch.setattr(tts_backend_windows.win32file, "ReadFile", fail_read)
    monkeypatch.setattr(tts_backend_windows.win32file, "CloseHandle", close)
    caplog.set_level(logging.ERROR, logger=tts.LOGGER.name)

    tts.read_pipe(stop_event=stop_event, reconnect_delay=0)

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert errors[0].getMessage() == "TTS pipe error; reconnecting"
    assert tts.CONNECTED is False


def test_tts_publisher_isolates_a_failing_item_subscriber(caplog) -> None:
    publisher = tts.Publisher()
    received = []

    def broken_subscriber(_data):
        msg = "subscriber failed"
        raise RuntimeError(msg)

    def healthy_subscriber(data):
        received.append(data)

    publisher.subscribe_item(broken_subscriber)
    publisher.subscribe_item(healthy_subscriber)
    caplog.set_level(logging.ERROR, logger=tts.LOGGER.name)
    try:
        publisher.publish_item(["test item"])
    finally:
        publisher.unsubscribe_item(broken_subscriber)
        publisher.unsubscribe_item(healthy_subscriber)

    assert received == [["test item"]]
    assert [record.getMessage() for record in caplog.records] == [f"TTS item subscriber failed: {broken_subscriber!r}"]
