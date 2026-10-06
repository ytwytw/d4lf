import importlib.util
import subprocess
import sys
import threading
from pathlib import Path
from queue import Queue
from textwrap import dedent

import pytest

if sys.platform != "win32":
    pytest.skip("Windows-only: shared UI thread requires a non-main-thread Tk root", allow_module_level=True)

from src import desktop as ui_thread
from src.desktop import ui_thread as implementation


@pytest.fixture
def isolated():
    """Never swap globals consulted by the live shared Tk thread used by other tests."""
    spec = importlib.util.spec_from_file_location("isolated_ui_thread", implementation.__file__)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_post_to_ui_thread_runs_on_shared_ui_thread() -> None:
    result = {}
    done = threading.Event()

    def record() -> None:
        result["thread"] = threading.current_thread()
        done.set()

    ui_thread.post_to_ui_thread(record)

    assert done.wait(timeout=2.0)
    assert result["thread"] is not threading.current_thread()
    assert result["thread"].name == "d4lf-ui-thread"


def test_call_on_ui_thread_returns_value() -> None:
    def add() -> int:
        assert threading.current_thread().name == "d4lf-ui-thread"
        return 1 + 1

    assert ui_thread.call_on_ui_thread(add) == 2


def test_call_on_ui_thread_propagates_exceptions() -> None:
    class BoomError(Exception):
        pass

    def raise_error() -> None:
        message = "boom"
        raise BoomError(message)

    with pytest.raises(BoomError):
        ui_thread.call_on_ui_thread(raise_error)


def test_get_root_returns_the_same_shared_root() -> None:
    assert ui_thread.get_root() is ui_thread.get_root()


def test_shutdown_does_not_create_tk_when_it_was_never_started(isolated) -> None:
    assert isolated._UI_THREAD is None

    assert isolated.shutdown_ui_thread()
    with pytest.raises(RuntimeError, match="shutting down"):
        isolated.ensure_ui_thread()


def test_shutdown_waits_boundedly_for_destroyed_windows_not_parked_owner(isolated, monkeypatch, mocker, caplog) -> None:
    thread = mocker.Mock()
    thread.is_alive.return_value = True
    monkeypatch.setattr(isolated, "_UI_THREAD", thread)
    stopped = mocker.Mock()
    stopped.wait.return_value = False
    monkeypatch.setattr(isolated, "_UI_STOPPED", stopped)

    assert not isolated.shutdown_ui_thread(timeout=0.1)

    stopped.wait.assert_called_once_with(timeout=0.1)
    thread.join.assert_not_called()
    assert "did not shut down" in caplog.text


def test_join_ui_thread_can_be_cancelled_without_waiting_for_tk(isolated, monkeypatch, mocker) -> None:
    stop = threading.Event()
    stop.set()
    thread = mocker.Mock()
    thread.is_alive.return_value = True
    monkeypatch.setattr(isolated, "_UI_THREAD", thread)
    monkeypatch.setattr(isolated, "ensure_ui_thread", lambda: None)

    isolated.join_ui_thread(stop)

    thread.join.assert_not_called()


def test_tk_owner_destroys_root_and_unblocks_pending_calls_on_shutdown(isolated, monkeypatch, mocker) -> None:
    root = mocker.Mock()
    stopping = threading.Event()
    stopping.set()
    pending = Queue()
    done = threading.Event()
    result = {}
    callback = mocker.Mock()
    pending.put((callback, done, result))
    monkeypatch.setattr(isolated.tk, "Tk", lambda: root)
    monkeypatch.setattr(isolated, "_UI_STOPPING", stopping)
    monkeypatch.setattr(isolated, "_UI_QUEUE", pending)
    retired = mocker.patch.object(isolated, "_retain_interpreter_until_process_exit")
    root.mainloop.side_effect = lambda: root.after.call_args_list[0].args[1]()

    isolated._tk_thread_main()

    root.quit.assert_called_once_with()
    root.destroy.assert_called_once_with()
    callback.assert_not_called()
    assert done.is_set()
    assert isinstance(result["error"], RuntimeError)
    assert isolated._UI_ROOT is None
    retired.assert_called_once_with(root)


def test_real_hidden_tk_shutdown_with_retained_resources_exits_cleanly() -> None:
    program = dedent("""
        import tkinter as tk
        from tkinter.font import Font
        from src.desktop import call_on_ui_thread, get_root, shutdown_ui_thread

        retained = []
        def create_resources():
            root = get_root()
            retained.extend([
                tk.Label(root, text="invisible shutdown test"),
                tk.StringVar(root, value="retained"),
                Font(root=root, size=10),
                tk.PhotoImage(master=root, width=1, height=1),
            ])
        call_on_ui_thread(create_resources)
        assert shutdown_ui_thread()
        try:
            call_on_ui_thread(lambda: None)
        except RuntimeError:
            print("resources retained; windows destroyed; late UI dispatch blocked")
        else:
            raise AssertionError("UI dispatch restarted after shutdown")
    """)
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert "windows destroyed; late UI dispatch blocked" in result.stdout
