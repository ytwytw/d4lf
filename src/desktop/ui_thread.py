"""Shared Tk UI thread. Every overlay subsystem attaches to this one root instead of creating its own tk.Tk()."""

import gc
import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter.font import Font

from src.type_aliases import JsonValue

LOGGER = logging.getLogger(__name__)

_UI_THREAD: threading.Thread | None = None
type UiResult = JsonValue | tk.Misc | BaseException
UiCallback = Callable[[], JsonValue | tk.Misc | None]
_UI_QUEUE: queue.Queue[tuple[UiCallback, threading.Event | None, dict[str, UiResult]]] = queue.Queue()
_UI_ROOT: tk.Tk | None = None
_UI_READY = threading.Event()
_START_LOCK = threading.Lock()
_UI_STOPPING = threading.Event()
_UI_STOPPED = threading.Event()


def _release_tk_resources(root: tk.Tk) -> None:
    """Finalize Tcl-backed resources on their owner, including externally retained handles."""
    for resource in gc.get_objects():
        if isinstance(resource, tk.Variable) and getattr(resource, "_tk", None) is root.tk:
            try:
                resource.__del__()  # ruff:ignore[unnecessary-dunder-call] - finalization must run on the Tcl owner
            except tk.TclError:
                LOGGER.debug("Tk variable was already removed", exc_info=True)
            finally:
                resource._tk = None
        elif isinstance(resource, Font) and getattr(resource, "_tk", None) is root.tk:
            resource.__del__()  # ruff:ignore[unnecessary-dunder-call] - finalization must run on the Tcl owner
            resource.delete_font = False
        elif isinstance(resource, tk.Image) and getattr(resource, "tk", None) is root.tk:
            resource.__del__()  # ruff:ignore[unnecessary-dunder-call] - finalization must run on the Tcl owner
            resource.name = None


def _retain_interpreter_until_process_exit(root: tk.Tk) -> None:
    """Keep Tcl owned by its daemon thread after windows and callbacks are destroyed.

    Overlay singletons may retain destroyed widgets. Releasing the final interpreter
    reference later on Qt's thread aborts Tcl. This retired owner does no UI work and
    holds the interpreter until normal process teardown; no caller joins it afterward.
    """
    threading.Event().wait()


def _tk_thread_main() -> None:
    """Own the shared Tk root and execute queued UI work on that thread."""
    global _UI_ROOT
    # Create a hidden root window. Overlay subsystems attach Toplevels to this
    # root, but Tk still needs one interpreter that owns the event loop.
    root = tk.Tk()
    root.withdraw()
    _UI_ROOT = root
    _UI_READY.set()

    def _pump_queue() -> None:
        """Run all queued UI callbacks and reschedule the queue pump."""
        if _UI_STOPPING.is_set():
            root.quit()
            return
        while True:
            try:
                fn, done, box = _UI_QUEUE.get_nowait()
            except queue.Empty:
                break

            try:
                box["result"] = fn()
            except Exception as exc:
                LOGGER.exception("Shared UI thread callback failed")
                box["error"] = exc
            finally:
                if done:
                    done.set()

        root.after(25, _pump_queue)

    root.after(0, _pump_queue)
    try:
        root.mainloop()
    finally:
        _release_tk_resources(root)
        root.destroy()
        _UI_ROOT = None
        _UI_READY.clear()
        while not _UI_QUEUE.empty():
            try:
                _, done, box = _UI_QUEUE.get_nowait()
            except queue.Empty:
                break
            box["error"] = RuntimeError("Shared Tk UI thread stopped")
            if done:
                done.set()
        gc.collect()
        _UI_STOPPED.set()
        _retain_interpreter_until_process_exit(root)


def ensure_ui_thread() -> None:
    """Start the shared Tk UI thread once and wait until it is ready."""
    global _UI_THREAD
    with _START_LOCK:
        if _UI_STOPPING.is_set():
            message = "Shared Tk UI thread is shutting down"
            raise RuntimeError(message)
        if _UI_THREAD is None or not _UI_THREAD.is_alive():
            _UI_READY.clear()
            _UI_THREAD = threading.Thread(target=_tk_thread_main, name="d4lf-ui-thread", daemon=True)
            _UI_THREAD.start()
    if not _UI_READY.wait(timeout=5.0):
        msg = "Shared Tk UI thread failed to init"
        raise RuntimeError(msg)


def get_root() -> tk.Tk:
    """Return the shared root, starting the UI thread first if needed."""
    ensure_ui_thread()
    if _UI_ROOT is None:
        message = "Shared Tk UI root is unavailable"
        raise RuntimeError(message)
    return _UI_ROOT


def join_ui_thread(stop_event: threading.Event | None = None) -> None:
    """Wait for the shared UI thread, or return when the application requests shutdown."""
    ensure_ui_thread()
    if _UI_THREAD is None:
        message = "Shared Tk UI thread is unavailable"
        raise RuntimeError(message)
    while _UI_THREAD.is_alive():
        if _UI_STOPPED.is_set():
            return
        if stop_event is not None and stop_event.is_set():
            return
        _UI_THREAD.join(timeout=0.1)


def shutdown_ui_thread(timeout: float = 5.0) -> bool:
    """Destroy Tk windows on their owner and wait boundedly for UI shutdown, not daemon retirement."""
    _UI_STOPPING.set()
    thread = _UI_THREAD
    if thread is None or not thread.is_alive():
        return True
    if thread is threading.current_thread():
        return _UI_STOPPED.is_set()
    if not _UI_STOPPED.wait(timeout=timeout):
        LOGGER.error("Shared Tk UI did not shut down within %.1f seconds", timeout)
        return False
    return True


def call_on_ui_thread(fn: UiCallback) -> JsonValue | tk.Misc | None:
    """Execute a callback on the Tk thread and wait for its return value."""
    ensure_ui_thread()
    if threading.current_thread() is _UI_THREAD:
        return fn()
    done = threading.Event()
    box: dict[str, UiResult] = {}
    _UI_QUEUE.put((fn, done, box))
    if not done.wait(timeout=5.0):
        message = "Shared Tk UI callback did not complete within 5 seconds"
        raise TimeoutError(message)
    exc = box.get("error")
    if isinstance(exc, BaseException):
        raise exc
    result = box.get("result")
    if isinstance(result, BaseException):
        raise result
    return result


def post_to_ui_thread(fn: UiCallback) -> None:
    """Queue work on the Tk thread without blocking the caller."""
    ensure_ui_thread()
    _UI_QUEUE.put((fn, None, {}))


def is_alive(w: tk.Misc | None, mapped: bool = False) -> bool:
    """Safely check if a widget exists (and optionally is mapped)."""
    try:
        return bool(w and w.winfo_exists() and (w.winfo_ismapped() if mapped else True))
    except tk.TclError:
        return False


def create_overlay_toplevel(parent: tk.Misc) -> tuple[tk.Toplevel, tk.Canvas]:
    """Create the fullscreen, click-through, transparent Toplevel+Canvas pair every overlay starts from."""
    root = tk.Toplevel(parent)
    root.overrideredirect(boolean=True)
    root.attributes("-topmost", 1)
    root.attributes("-transparentcolor", "white")
    root.attributes("-alpha", 1.0)
    canvas = tk.Canvas(root, bg="white", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    return root, canvas
