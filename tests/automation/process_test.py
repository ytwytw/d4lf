import psutil

from src.automation import process as _process


def test_safe_exit_delegates_to_process_exit(monkeypatch) -> None:
    called = []
    inspected = []
    monkeypatch.setattr(psutil, "process_iter", lambda *_args: inspected.append(True) or [])
    monkeypatch.setattr(_process.os, "_exit", lambda code: called.append(code))
    _process.safe_exit(7)
    assert called == [7]
    assert inspected == []
