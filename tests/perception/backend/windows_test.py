import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named-pipe adapter")


def test_windows_backend_module_is_only_exercised_on_windows() -> None:
    from src.perception.backend.windows import WindowsTTSBackend  # ruff:ignore[import-outside-top-level]

    assert WindowsTTSBackend.__name__ == "WindowsTTSBackend"


def test_windows_backend_reconnects_after_a_pipe_read_error(monkeypatch) -> None:
    from src.perception.backend import windows  # ruff:ignore[import-outside-top-level]

    class StopBackendError(Exception):
        pass

    handles = iter([123])
    closed = []
    connected = []
    logger = SimpleNamespace(debug=lambda *_args: None, info=lambda *_args: None, exception=lambda *_args: None)

    def create_pipe():
        try:
            return next(handles)
        except StopIteration as error:
            raise StopBackendError from error

    monkeypatch.setattr(windows.win32pipe, "ConnectNamedPipe", lambda *_args: None)
    monkeypatch.setattr(windows.win32file, "ReadFile", lambda *_args: (_ for _ in ()).throw(OSError("broken pipe")))
    monkeypatch.setattr(windows.win32file, "CloseHandle", closed.append)

    with pytest.raises(StopBackendError):
        windows.WindowsTTSBackend().read_pipe(create_pipe, object(), logger, connected.append)

    assert closed == [123]
    assert connected == [True, False]
