import json
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

from src.tools.tts_capture import (
    SCHEMA_VERSION,
    AtomicJsonlWriter,
    CaptureSession,
    NamedPipeError,
    PipeDisconnectedError,
    TtsCaptureRecorder,
    WindowsNamedPipeSource,
    build_argument_parser,
    build_capture_record,
    decode_dll_message,
)


class _CollectingWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write(self, record: Mapping[str, object]) -> None:
        self.records.append(dict(record))


class _FakeMessageSource:
    def __init__(self, payloads: list[bytes]) -> None:
        self.payloads = payloads
        self.closed = False

    def messages(self, stop_event: threading.Event) -> Iterator[bytes]:
        for payload in self.payloads:
            if stop_event.is_set():
                return
            yield payload

    def close(self) -> None:
        self.closed = True


def test_recorder_writes_every_raw_utf8_message_without_item_boundaries() -> None:
    payloads = [b"CONNECTED\0", "先祖传奇双手剑\0".encode(), b"Mouse Button 4\0", "  &apos;保持原样  \0".encode()]
    source = _FakeMessageSource(payloads)
    writer = _CollectingWriter()
    timestamps = iter([
        datetime(2026, 7, 10, 14, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 10, 14, 0, 1, tzinfo=UTC),
        datetime(2026, 7, 10, 14, 0, 2, tzinfo=UTC),
        datetime(2026, 7, 10, 14, 0, 3, tzinfo=UTC),
    ])
    session = CaptureSession(
        session_id="capture-session", started_at="2026-07-10T13:59:00.000Z", metadata={"area": "inventory"}
    )
    recorder = TtsCaptureRecorder(
        source=source,
        writer=writer,
        locale="zhCN",
        game_build="2.4.1.12345",
        session=session,
        clock=lambda: next(timestamps),
    )

    count = recorder.run(threading.Event())

    assert count == 4
    assert source.closed
    assert [record["raw_text"] for record in writer.records] == [
        "CONNECTED",
        "先祖传奇双手剑",
        "Mouse Button 4",
        "  &apos;保持原样  ",
    ]
    assert [record["sequence"] for record in writer.records] == [1, 2, 3, 4]
    assert [record["timestamp"] for record in writer.records] == [
        "2026-07-10T14:00:00.000Z",
        "2026-07-10T14:00:01.000Z",
        "2026-07-10T14:00:02.000Z",
        "2026-07-10T14:00:03.000Z",
    ]
    assert all(record["schema_version"] == SCHEMA_VERSION for record in writer.records)
    assert all(record["locale"] == "zhCN" for record in writer.records)
    assert all(record["game_build"] == "2.4.1.12345" for record in writer.records)
    assert all(
        record["session"]
        == {
            "id": "capture-session",
            "started_at": "2026-07-10T13:59:00.000Z",
            "pipe_name": r"\\.\pipe\d4lf",
            "metadata": {"area": "inventory"},
        }
        for record in writer.records
    )


def test_decode_removes_only_the_dll_transport_terminator() -> None:
    payload = "  中文\0仍然是原文  \0".encode()

    assert decode_dll_message(payload) == "  中文\0仍然是原文  "


def test_shared_record_builder_matches_the_capture_schema() -> None:
    session = CaptureSession(session_id="shared", started_at="2026-07-10T20:00:00.000Z")

    record = build_capture_record(
        payload="原始文本\0".encode(),
        locale="zhCN",
        game_build="3.1.0.72698",
        session=session,
        sequence=7,
        captured_at=datetime(2026, 7, 10, 20, 0, 1, tzinfo=UTC),
    )

    assert record == {
        "schema_version": SCHEMA_VERSION,
        "locale": "zhCN",
        "game_build": "3.1.0.72698",
        "session": session.as_json(),
        "sequence": 7,
        "timestamp": "2026-07-10T20:00:01.000Z",
        "raw_text": "原始文本",
    }


def test_atomic_jsonl_writer_replaces_destination_only_after_commit(tmp_path: Path) -> None:
    destination = tmp_path / "capture.jsonl"
    destination.write_text('{"old":true}\n', encoding="utf-8")

    with AtomicJsonlWriter(destination) as writer:
        writer.write({"sequence": 1, "raw_text": "传奇物品"})
        writer.write({"sequence": 2, "raw_text": "第二行"})
        assert destination.read_text(encoding="utf-8") == '{"old":true}\n'

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"sequence": 1, "raw_text": "传奇物品"},
        {"sequence": 2, "raw_text": "第二行"},
    ]
    assert not list(tmp_path.glob(".capture.jsonl.*.tmp"))


def _write_interrupted_capture(destination: Path) -> None:
    message = "capture interrupted"
    with AtomicJsonlWriter(destination) as writer:
        writer.write({"sequence": 1, "raw_text": "不会提交"})
        raise RuntimeError(message)


def test_atomic_jsonl_writer_keeps_destination_on_failure(tmp_path: Path) -> None:
    destination = tmp_path / "capture.jsonl"
    destination.write_text('{"old":true}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="capture interrupted"):
        _write_interrupted_capture(destination)

    assert destination.read_text(encoding="utf-8") == '{"old":true}\n'
    assert not list(tmp_path.glob(".capture.jsonl.*.tmp"))


class _FakeNamedPipeApi:
    def __init__(self, stop_event: threading.Event) -> None:
        self.stop_event = stop_event
        self.create_count = 0
        self.connect_attempts: dict[object, int] = {}
        self.read_attempts: dict[object, int] = {}
        self.disconnected: list[object] = []
        self.closed: list[object] = []

    def create_server(self, pipe_name: str) -> object:
        assert pipe_name == r"\\.\pipe\d4lf"
        self.create_count += 1
        return f"pipe-{self.create_count}"

    def try_connect(self, handle: object) -> bool:
        attempts = self.connect_attempts.get(handle, 0) + 1
        self.connect_attempts[handle] = attempts
        return attempts > 1

    def read_message(self, handle: object) -> bytes | None:
        attempts = self.read_attempts.get(handle, 0) + 1
        self.read_attempts[handle] = attempts
        if handle == "pipe-1":
            if attempts == 1:
                return "第一条\0".encode()
            raise PipeDisconnectedError
        self.stop_event.set()
        return "重连后的消息\0".encode()

    def disconnect(self, handle: object) -> None:
        self.disconnected.append(handle)

    def close(self, handle: object) -> None:
        self.closed.append(handle)


def test_named_pipe_source_is_injectable_and_reconnects_cleanly() -> None:
    stop_event = threading.Event()
    api = _FakeNamedPipeApi(stop_event)
    source = WindowsNamedPipeSource(api=api, poll_interval=0.0001)

    messages = list(source.messages(stop_event))

    assert messages == ["第一条\0".encode(), "重连后的消息\0".encode()]
    assert api.connect_attempts == {"pipe-1": 2, "pipe-2": 2}
    assert api.disconnected == ["pipe-1", "pipe-2"]
    assert api.closed == ["pipe-1", "pipe-2"]


class _DisconnectFailingApi:
    def __init__(self, stop_event: threading.Event) -> None:
        self.stop_event = stop_event
        self.closed = False

    def create_server(self, pipe_name: str) -> object:
        return pipe_name

    def try_connect(self, handle: object) -> bool:
        return True

    def read_message(self, handle: object) -> bytes | None:
        self.stop_event.set()
        return b"message\0"

    def disconnect(self, handle: object) -> None:
        message = "disconnect failed"
        raise NamedPipeError(message)

    def close(self, handle: object) -> None:
        self.closed = True


def test_named_pipe_handle_closes_when_disconnect_fails() -> None:
    stop_event = threading.Event()
    api = _DisconnectFailingApi(stop_event)
    source = WindowsNamedPipeSource(api=api)

    with pytest.raises(NamedPipeError, match="disconnect failed"):
        list(source.messages(stop_event))

    assert api.closed


def test_cli_requires_explicit_capture_identity() -> None:
    arguments = build_argument_parser().parse_args([
        "--output",
        "capture.jsonl",
        "--locale",
        "zhCN",
        "--game-build",
        "2.4.1.12345",
        "--session-meta",
        "area=inventory",
        "--session-meta",
        "character=rogue",
    ])

    assert arguments.locale == "zhCN"
    assert arguments.game_build == "2.4.1.12345"
    assert arguments.session_meta == [("area", "inventory"), ("character", "rogue")]
