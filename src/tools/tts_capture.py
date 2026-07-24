from __future__ import annotations

import argparse
import importlib
import json
import os
import signal
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Never, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence
    from types import FrameType, ModuleType
    from typing import Self

    SignalHandler = Callable[[int, FrameType | None], object] | int | None

SCHEMA_VERSION = 1
DEFAULT_PIPE_NAME = r"\\.\pipe\d4lf"
DEFAULT_POLL_INTERVAL_SECONDS = 0.05

_ERROR_ACCESS_DENIED = 5
_ERROR_BROKEN_PIPE = 109
_ERROR_NO_DATA = 232
_ERROR_PIPE_NOT_CONNECTED = 233
_ERROR_MORE_DATA = 234
_ERROR_PIPE_BUSY = 231
_ERROR_PIPE_CONNECTED = 535
_ERROR_PIPE_LISTENING = 536
_DISCONNECTED_ERRORS = {_ERROR_BROKEN_PIPE, _ERROR_NO_DATA, _ERROR_PIPE_NOT_CONNECTED}


class PipeDisconnectedError(Exception):
    pass


class NamedPipeError(RuntimeError):
    pass


class NamedPipeApi(Protocol):
    def create_server(self, pipe_name: str) -> object: ...

    def try_connect(self, handle: object) -> bool: ...

    def read_message(self, handle: object) -> bytes | None: ...

    def disconnect(self, handle: object) -> None: ...

    def close(self, handle: object) -> None: ...


class MessageSource(Protocol):
    def messages(self, stop_event: threading.Event) -> Iterator[bytes]: ...

    def close(self) -> None: ...


class RecordWriter(Protocol):
    def write(self, record: Mapping[str, object]) -> None: ...


def _winerror_code(error: BaseException) -> int | None:
    if not error.args:
        return None
    code = error.args[0]
    return code if isinstance(code, int) else None


class PyWin32NamedPipeApi:
    def __init__(self) -> None:
        if sys.platform != "win32":
            msg = "The TTS named-pipe recorder is available only on Windows."
            raise OSError(msg)

        self._pywintypes: ModuleType = importlib.import_module("pywintypes")
        self._win32file: ModuleType = importlib.import_module("win32file")
        self._win32pipe: ModuleType = importlib.import_module("win32pipe")

    def create_server(self, pipe_name: str) -> object:
        try:
            return self._win32pipe.CreateNamedPipe(
                pipe_name,
                self._win32pipe.PIPE_ACCESS_INBOUND,
                self._win32pipe.PIPE_TYPE_MESSAGE | self._win32pipe.PIPE_READMODE_MESSAGE | self._win32pipe.PIPE_NOWAIT,
                1,
                65536,
                65536,
                0,
                None,
            )
        except self._pywintypes.error as error:
            code = _winerror_code(error)
            if code in {_ERROR_ACCESS_DENIED, _ERROR_PIPE_BUSY}:
                msg = f"Cannot listen on {pipe_name!r}; another D4LF TTS listener may already be running."
                raise NamedPipeError(msg) from error
            msg = f"Could not create named pipe {pipe_name!r} (Windows error {code})."
            raise NamedPipeError(msg) from error

    def try_connect(self, handle: object) -> bool:
        try:
            self._win32pipe.ConnectNamedPipe(handle, None)
        except self._pywintypes.error as error:
            code = _winerror_code(error)
            if code == _ERROR_PIPE_CONNECTED:
                return True
            if code == _ERROR_PIPE_LISTENING:
                return False
            if code in _DISCONNECTED_ERRORS:
                raise PipeDisconnectedError from error
            msg = f"Could not accept the TTS pipe connection (Windows error {code})."
            raise NamedPipeError(msg) from error
        return True

    def read_message(self, handle: object) -> bytes | None:
        message_size = 0
        try:
            _, _, message_size = self._win32pipe.PeekNamedPipe(handle, 0)
        except self._pywintypes.error as error:
            self._raise_read_error(error)

        if message_size == 0:
            return None

        chunks: list[bytes] = []
        while message_size > 0:
            status = 0
            data = b""
            try:
                status, data = self._win32file.ReadFile(handle, message_size, None)
            except self._pywintypes.error as error:
                self._raise_read_error(error)
            chunks.append(bytes(data))
            if status == 0:
                break
            if status != _ERROR_MORE_DATA:
                msg = f"Could not read the TTS pipe message (Windows error {status})."
                raise NamedPipeError(msg)
            try:
                _, _, message_size = self._win32pipe.PeekNamedPipe(handle, 0)
            except self._pywintypes.error as error:
                self._raise_read_error(error)
        return b"".join(chunks)

    def disconnect(self, handle: object) -> None:
        try:
            self._win32pipe.DisconnectNamedPipe(handle)
        except self._pywintypes.error as error:
            if _winerror_code(error) not in _DISCONNECTED_ERRORS:
                code = _winerror_code(error)
                msg = f"Could not disconnect the TTS pipe (Windows error {code})."
                raise NamedPipeError(msg) from error

    def close(self, handle: object) -> None:
        try:
            self._win32file.CloseHandle(handle)
        except self._pywintypes.error as error:
            code = _winerror_code(error)
            msg = f"Could not close the TTS pipe (Windows error {code})."
            raise NamedPipeError(msg) from error

    @staticmethod
    def _raise_read_error(error: BaseException) -> Never:
        code = _winerror_code(error)
        if code in _DISCONNECTED_ERRORS:
            raise PipeDisconnectedError from error
        msg = f"Could not read the TTS pipe (Windows error {code})."
        raise NamedPipeError(msg) from error


class WindowsNamedPipeSource:
    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        *,
        api: NamedPipeApi | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        if poll_interval <= 0:
            msg = "poll_interval must be greater than zero"
            raise ValueError(msg)
        self._pipe_name = pipe_name
        self._api = api or PyWin32NamedPipeApi()
        self._poll_interval = poll_interval
        self._closed = threading.Event()
        self._handle_lock = threading.Lock()
        self._handle: object | None = None

    def messages(self, stop_event: threading.Event) -> Iterator[bytes]:
        while not self._should_stop(stop_event):
            handle = self._api.create_server(self._pipe_name)
            if not self._adopt_handle(handle):
                self._api.close(handle)
                return

            connected = False
            try:
                while not self._should_stop(stop_event):
                    try:
                        connected = self._api.try_connect(handle)
                    except PipeDisconnectedError:
                        break
                    if connected:
                        break
                    stop_event.wait(self._poll_interval)

                while connected and not self._should_stop(stop_event):
                    try:
                        message = self._api.read_message(handle)
                    except PipeDisconnectedError:
                        break
                    if message is None:
                        stop_event.wait(self._poll_interval)
                        continue
                    yield message
            finally:
                if self._release_handle(handle):
                    try:
                        if connected:
                            self._api.disconnect(handle)
                    finally:
                        self._api.close(handle)

    def close(self) -> None:
        self._closed.set()
        with self._handle_lock:
            handle = self._handle
            self._handle = None
        if handle is not None:
            self._api.close(handle)

    def _should_stop(self, stop_event: threading.Event) -> bool:
        return self._closed.is_set() or stop_event.is_set()

    def _adopt_handle(self, handle: object) -> bool:
        with self._handle_lock:
            if self._closed.is_set():
                return False
            self._handle = handle
            return True

    def _release_handle(self, handle: object) -> bool:
        with self._handle_lock:
            if self._handle is not handle:
                return False
            self._handle = None
            return True


@dataclass(frozen=True, slots=True)
class CaptureSession:
    session_id: str
    started_at: str
    pipe_name: str = DEFAULT_PIPE_NAME
    metadata: Mapping[str, str] = field(default_factory=dict)

    def as_json(self) -> dict[str, object]:
        return {
            "id": self.session_id,
            "started_at": self.started_at,
            "pipe_name": self.pipe_name,
            "metadata": dict(self.metadata),
        }


def utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = "Capture timestamps must be timezone-aware."
        raise ValueError(msg)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def utc_now() -> datetime:
    return datetime.now(UTC)


def decode_dll_message(payload: bytes) -> str:
    if payload.endswith(b"\x00"):
        payload = payload[:-1]
    return payload.decode("utf-8")


def build_capture_record(
    *, payload: bytes, locale: str, game_build: str, session: CaptureSession, sequence: int, captured_at: datetime
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "locale": locale,
        "game_build": game_build,
        "session": session.as_json(),
        "sequence": sequence,
        "timestamp": utc_timestamp(captured_at),
        "raw_text": decode_dll_message(payload),
    }


class TtsCaptureRecorder:
    def __init__(
        self,
        *,
        source: MessageSource,
        writer: RecordWriter,
        locale: str,
        game_build: str,
        session: CaptureSession,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._source = source
        self._writer = writer
        self._locale = locale
        self._game_build = game_build
        self._session = session
        self._clock = clock
        self.sequence = 0

    def run(self, stop_event: threading.Event) -> int:
        try:
            for payload in self._source.messages(stop_event):
                self.sequence += 1
                self._writer.write(
                    build_capture_record(
                        payload=payload,
                        locale=self._locale,
                        game_build=self._game_build,
                        session=self._session,
                        sequence=self.sequence,
                        captured_at=self._clock(),
                    )
                )
        finally:
            self._source.close()
        return self.sequence


class AtomicJsonlWriter:
    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self._file_descriptor: int | None = None
        self._temporary_path: Path | None = None

    def __enter__(self) -> Self:
        return self.open()

    def open(self) -> Self:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.destination.parent, prefix=f".{self.destination.name}.", suffix=".tmp"
        )
        self._file_descriptor = file_descriptor
        self._temporary_path = Path(temporary_name)
        return self

    def __exit__(self, exception_type, exception, traceback) -> bool:
        if exception_type is None:
            self.commit()
        else:
            self.abort()
        return False

    def write(self, record: Mapping[str, object]) -> None:
        if self._file_descriptor is None:
            msg = "The JSONL writer is not open."
            raise RuntimeError(msg)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        remaining = memoryview(line)
        while remaining:
            written = os.write(self._file_descriptor, remaining)
            if written == 0:
                msg = "Could not write the JSONL record."
                raise OSError(msg)
            remaining = remaining[written:]

    def commit(self) -> None:
        file_descriptor, temporary_path = self._open_state()
        try:
            os.fsync(file_descriptor)
            os.close(file_descriptor)
            self._file_descriptor = None
            temporary_path.replace(self.destination)
            self._temporary_path = None
        except OSError:
            if self._file_descriptor is not None:
                os.close(self._file_descriptor)
                self._file_descriptor = None
            temporary_path.unlink(missing_ok=True)
            self._temporary_path = None
            raise

    def abort(self) -> None:
        if self._file_descriptor is not None:
            os.close(self._file_descriptor)
            self._file_descriptor = None
        if self._temporary_path is not None:
            self._temporary_path.unlink(missing_ok=True)
            self._temporary_path = None

    def _open_state(self) -> tuple[int, Path]:
        if self._file_descriptor is None or self._temporary_path is None:
            msg = "The JSONL writer is not open."
            raise RuntimeError(msg)
        return self._file_descriptor, self._temporary_path


def _session_metadata(value: str) -> tuple[str, str]:
    key, separator, metadata_value = value.partition("=")
    key = key.strip()
    if not separator or not key:
        msg = "session metadata must use KEY=VALUE with a non-empty key"
        raise argparse.ArgumentTypeError(msg)
    return key, metadata_value


def _non_empty(value: str) -> str:
    value = value.strip()
    if not value:
        msg = "value must not be empty"
        raise argparse.ArgumentTypeError(msg)
    return value


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record raw UTF-8 messages from saapi64.dll without parsing or controlling the game."
    )
    parser.add_argument("--output", required=True, type=Path, help="Destination JSONL file")
    parser.add_argument("--locale", required=True, type=_non_empty, help="Game locale, for example zhCN")
    parser.add_argument("--game-build", required=True, type=_non_empty, help="Exact Diablo IV game build")
    parser.add_argument(
        "--session-meta",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        type=_session_metadata,
        help="Optional session metadata; may be repeated",
    )
    return parser


@contextmanager
def _stop_on_console_signal(stop_event: threading.Event) -> Iterator[None]:
    watched_signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        watched_signals.append(signal.SIGBREAK)

    previous_handlers: dict[signal.Signals, SignalHandler] = {}

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()

    try:
        for watched_signal in watched_signals:
            previous_handlers[watched_signal] = signal.getsignal(watched_signal)
            signal.signal(watched_signal, request_stop)
        yield
    finally:
        for watched_signal, previous_handler in previous_handlers.items():
            signal.signal(watched_signal, previous_handler)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    if sys.platform != "win32":
        print("The TTS named-pipe recorder is available only on Windows.", file=sys.stderr)
        return 2

    stop_event = threading.Event()
    started_at = utc_timestamp(utc_now())
    session = CaptureSession(session_id=str(uuid.uuid4()), metadata=dict(arguments.session_meta), started_at=started_at)
    source = WindowsNamedPipeSource()
    recorder: TtsCaptureRecorder | None = None

    print(f"Listening on {DEFAULT_PIPE_NAME}. Press Ctrl+C to stop cleanly.", file=sys.stderr)
    try:
        with _stop_on_console_signal(stop_event), AtomicJsonlWriter(arguments.output) as writer:
            recorder = TtsCaptureRecorder(
                source=source, writer=writer, locale=arguments.locale, game_build=arguments.game_build, session=session
            )
            recorder.run(stop_event)
    except (ModuleNotFoundError, NamedPipeError, OSError, UnicodeError, ValueError) as error:
        print(f"Capture failed: {error}", file=sys.stderr)
        return 1

    record_count = recorder.sequence if recorder is not None else 0
    print(f"Saved {record_count} messages to {arguments.output}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
