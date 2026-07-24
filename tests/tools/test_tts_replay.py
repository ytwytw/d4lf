from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from src.tools.tts_replay import DEFAULT_MAX_LINES, ReplayError, load_assets, main, replay_capture


def _write_assets(path: Path) -> Path:
    path.mkdir()
    (path / "grammar.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "labels": {
                    "item_end_control": ["鼠标左键"],
                    "item_name_prefix": ["[收藏物品]."],
                    "item_power": ["物品强度"],
                    "item_start_ignored": ["词缀"],
                },
                "identifiers": {},
                "rarities": {"Legendary": ["传奇"], "Unique": ["暗金"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (path / "item_types.json").write_text(
        json.dumps({"Ring": "戒指", "Sword2H": "双手剑"}, ensure_ascii=False), encoding="utf-8"
    )
    return path


def test_replay_allows_only_declared_non_equipment_empty_aliases(tmp_path: Path) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    item_types_path = assets_dir / "item_types.json"
    item_types = json.loads(item_types_path.read_text(encoding="utf-8"))
    item_types["Tome"] = ""
    item_types_path.write_text(json.dumps(item_types, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ReplayError, match="undeclared empty alias"):
        load_assets(assets_dir, locale="zhCN")

    (assets_dir / "quality-report.json").write_text(
        json.dumps({"scope": {"excluded_item_types": ["Tome"]}}), encoding="utf-8"
    )

    assets = load_assets(assets_dir, locale="zhCN")

    assert assets.catalog.resolve_item_type("Tome") == "Tome"
    assert assets.quality_report_sha256 is not None


def test_committed_zhcn_candidate_assets_load_for_offline_replay() -> None:
    assets = load_assets(Path(__file__).resolve().parents[2] / "assets" / "lang" / "zhCN", locale="zhCN")

    assert assets.catalog.resolve_item_type("梦魇符印") == "Sigil"
    assert assets.quality_report_sha256 is not None


def _record(
    sequence: int, raw_text: object, *, locale: str = "zhCN", game_build: str = "3.1.0.72698"
) -> dict[str, object]:
    return {"schema_version": 1, "locale": locale, "game_build": game_build, "sequence": sequence, "raw_text": raw_text}


def _write_capture(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def test_replay_frames_adjacent_chinese_rarity_and_type_with_original_records(tmp_path: Path) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    capture_path = _write_capture(
        tmp_path / "capture.jsonl",
        [
            _record(10, "背包"),
            _record(20, "星辰指环"),
            _record(30, "传奇戒指"),
            _record(40, "925 物品强度"),
            _record(50, "鼠标左键"),
        ],
    )

    report = replay_capture(capture_path, assets_dir)
    report_input = report["input"]
    assert isinstance(report_input, dict)
    report_input = cast("dict[str, object]", report_input)

    assert report_input == {
        "sha256": report_input["sha256"],
        "schema_version": 1,
        "locale": "zhCN",
        "game_build": "3.1.0.72698",
        "first_sequence": 10,
        "last_sequence": 50,
    }
    assert report["record_count"] == 5
    assert report["frame_count"] == 1
    assert report["frames"] == [
        {
            "start_sequence": 20,
            "end_sequence": 50,
            "records": [
                {"sequence": 20, "raw_text": "星辰指环"},
                {"sequence": 30, "raw_text": "传奇戒指"},
                {"sequence": 40, "raw_text": "925 物品强度"},
                {"sequence": 50, "raw_text": "鼠标左键"},
            ],
        }
    ]
    assert report["unframed_tail"] == []


def test_replay_matches_online_cleanup_and_skips_empty_payloads(tmp_path: Path) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    capture_path = _write_capture(
        tmp_path / "capture.jsonl",
        [
            _record(1, ""),
            _record(2, "[收藏物品]. 星辉指环"),
            _record(3, "传奇戒指"),
            _record(4, "925 物品强度"),
            _record(5, ""),
            _record(6, "鼠标左键"),
        ],
    )

    report = replay_capture(capture_path, assets_dir)
    frames = report["frames"]
    assert isinstance(frames, list)
    assert frames
    first_frame = frames[0]
    assert isinstance(first_frame, dict)
    first_frame = cast("dict[str, object]", first_frame)

    assert report["record_count"] == 6
    assert report["frame_count"] == 1
    assert first_frame["records"] == [
        {"sequence": 2, "raw_text": "[收藏物品]. 星辉指环"},
        {"sequence": 3, "raw_text": "传奇戒指"},
        {"sequence": 4, "raw_text": "925 物品强度"},
        {"sequence": 6, "raw_text": "鼠标左键"},
    ]


def test_replay_bounds_noise_and_reports_only_the_unframed_tail(tmp_path: Path) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    records = [_record(sequence, f"噪声 {sequence}") for sequence in range(1, DEFAULT_MAX_LINES + 18)]
    capture_path = _write_capture(tmp_path / "capture.jsonl", records)

    report = replay_capture(capture_path, assets_dir)

    tail = report["unframed_tail"]
    assert isinstance(tail, list)
    tail = cast("list[object]", tail)
    assert len(tail) == DEFAULT_MAX_LINES
    assert tail[0] == {"sequence": 18, "raw_text": "噪声 18"}
    assert tail[-1] == {"sequence": DEFAULT_MAX_LINES + 17, "raw_text": f"噪声 {DEFAULT_MAX_LINES + 17}"}
    assert report["frame_count"] == 0


@pytest.mark.parametrize(
    ("records", "error_code"),
    [
        ([_record(1, "第一行"), _record(2, "第二行", locale="enUS")], "mixed_locale"),
        ([_record(1, "第一行"), _record(2, "第二行", game_build="3.1.0.99999")], "mixed_game_build"),
    ],
)
def test_replay_rejects_mixed_capture_identity(
    tmp_path: Path, records: list[dict[str, object]], error_code: str
) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    capture_path = _write_capture(tmp_path / "capture.jsonl", records)

    with pytest.raises(ReplayError, match=rf"^{error_code} at line 2:"):
        replay_capture(capture_path, assets_dir)


def test_replay_rejects_bad_json_with_stable_line_error(tmp_path: Path) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    capture_path = tmp_path / "capture.jsonl"
    capture_path.write_text(json.dumps(_record(1, "第一行"), ensure_ascii=False) + "\n{bad json}\n", encoding="utf-8")

    with pytest.raises(ReplayError, match=r"^invalid_json at line 2:"):
        replay_capture(capture_path, assets_dir)


@pytest.mark.parametrize(
    ("sequences", "error_code"), [([1, 2, 2], "duplicate_sequence"), ([1, 3, 2], "non_monotonic_sequence")]
)
def test_replay_rejects_duplicate_or_non_monotonic_sequences(
    tmp_path: Path, sequences: list[int], error_code: str
) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    capture_path = _write_capture(
        tmp_path / "capture.jsonl", [_record(sequence, f"记录 {index}") for index, sequence in enumerate(sequences)]
    )

    with pytest.raises(ReplayError, match=rf"^{error_code} at line 3:"):
        replay_capture(capture_path, assets_dir)


@pytest.mark.parametrize(
    ("replacement", "error_code"),
    [
        ({"schema_version": 2}, "unsupported_schema"),
        ({"raw_text": ["不是字符串"]}, "invalid_raw_text"),
        ({"locale": ""}, "invalid_field"),
        ({"game_build": None}, "invalid_field"),
    ],
)
def test_replay_strictly_validates_capture_fields(
    tmp_path: Path, replacement: dict[str, object], error_code: str
) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    record = _record(1, "第一行")
    record.update(replacement)
    capture_path = _write_capture(tmp_path / "capture.jsonl", [record])

    with pytest.raises(ReplayError, match=rf"^{error_code} at line 1:"):
        replay_capture(capture_path, assets_dir)


def test_cli_writes_deterministic_utf8_report_and_returns_nonzero_on_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assets_dir = _write_assets(tmp_path / "assets")
    capture_path = _write_capture(
        tmp_path / "capture.jsonl", [_record(1, "星辰指环"), _record(2, "暗金戒指"), _record(3, "鼠标左键")]
    )
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"

    first_result = main(["--input", str(capture_path), "--assets-dir", str(assets_dir), "--output", str(first_output)])
    second_result = main([
        "--input",
        str(capture_path),
        "--assets-dir",
        str(assets_dir),
        "--output",
        str(second_output),
    ])

    assert first_result == second_result == 0
    assert first_output.read_bytes() == second_output.read_bytes()
    assert "暗金戒指".encode() in first_output.read_bytes()
    assert "timestamp" not in first_output.read_text(encoding="utf-8")

    invalid_capture = tmp_path / "invalid.jsonl"
    invalid_capture.write_text("not-json\n", encoding="utf-8")
    preserved_output = tmp_path / "preserved.json"
    preserved_output.write_text("keep me", encoding="utf-8")
    result = main(["--input", str(invalid_capture), "--assets-dir", str(assets_dir), "--output", str(preserved_output)])

    assert result == 1
    assert preserved_output.read_text(encoding="utf-8") == "keep me"
    assert "Replay failed: invalid_json at line 1:" in capsys.readouterr().err


def test_replay_uses_only_the_explicit_assets_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets_dir = _write_assets(tmp_path / "explicit-assets")
    capture_path = _write_capture(tmp_path / "capture.jsonl", [_record(1, "噪声")])
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".d4lf").mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    report = replay_capture(capture_path, assets_dir)

    assert report["record_count"] == 1


def test_import_isolated_from_config_input_and_named_pipe_dependencies(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    environment = os.environ.copy()
    environment.update({"HOME": str(fake_home), "USERPROFILE": str(fake_home)})
    script = (
        "import pathlib\n"
        "import sys\n"
        "import src.tools.tts_replay\n"
        "blocked = {'keyboard', 'mouse', 'pywintypes', 'win32file', 'win32pipe'} & sys.modules.keys()\n"
        "assert not blocked, sorted(blocked)\n"
        "assert 'src.tts' not in sys.modules\n"
        "assert 'src.config.helper' not in sys.modules\n"
        "assert 'src.config.loader' not in sys.modules\n"
        "assert not (pathlib.Path.home() / '.d4lf').exists()\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
