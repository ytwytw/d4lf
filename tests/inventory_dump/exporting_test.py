import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.inventory_dump.exporting import SnapshotWriter, render_document, serialize_item
from src.inventory_dump.models import ExportFormat, ItemRecord, Location, ScanDocument
from src.item import Affix, AffixType, Item, SeasonalAttribute


def test_item_serialization_preserves_original_name_zero_and_seasonal_data() -> None:
    item = Item(original_name="原始物品", power=0, seasonal_attribute=SeasonalAttribute.sanctified, is_in_shop=True)
    item.affixes = [Affix(name="strength", type=AffixType.rerolled, value=0)]
    data = serialize_item(item)
    assert data["original_name"] == "原始物品"
    assert data["seasonal_attribute"] == "sanctified"
    assert data["is_in_shop"] is True
    assert data["power"] == 0
    affixes = data["affixes"]
    assert isinstance(affixes, list)
    affix = affixes[0]
    assert isinstance(affix, dict)
    assert affix["type"] == "rerolled"
    assert affix["value"] == 0


@pytest.mark.parametrize("output_format", list(ExportFormat))
def test_every_format_preserves_identical_complete_data(output_format) -> None:
    document = ScanDocument("zhCN", "test", status="partial")
    document.items.append(
        ItemRecord(
            Location("stash", "2", "r01c01", (10, 20)),
            favorite=True,
            junk=True,
            status="parse_error",
            raw_tts=["[垃圾] 原始", "词缀：25%"],
            error="Unknown unique",
            favorite_evidence=[
                {"source": "slot_screenshot_brightness", "verification": "unverified", "value": False},
                {
                    "source": "raw_tts_title",
                    "verification": "explicit_marker",
                    "value": True,
                    "text": "[收藏物品]. 原始",
                },
            ],
        )
    )
    rendered = render_document(document, output_format)
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(rendered[rendered.index("{") :])
    assert payload == json.loads(json.dumps(asdict(document)))


def test_interrupted_write_preserves_last_readable_snapshot(tmp_path, monkeypatch) -> None:
    path = tmp_path / "snapshot.json"
    writer = SnapshotWriter(path, ExportFormat.JSON)
    document = ScanDocument("enUS", "test")
    writer.save(document)
    old = path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        "src.inventory_dump.exporting.render_document", lambda *_: (_ for _ in ()).throw(OSError("disk"))
    )
    with pytest.raises(OSError, match="disk"):
        writer.save(document)
    assert path.read_text(encoding="utf-8") == old


@pytest.mark.parametrize("output_format", [ExportFormat.MARKDOWN, ExportFormat.TEXT])
def test_unknown_item_title_uses_observed_name_and_retains_parser_failure(output_format) -> None:
    document = ScanDocument("zhCN", "test", status="partial")
    document.items.append(
        ItemRecord(
            Location("stash", "1", "r01c01", (10, 20)),
            status="parse_error",
            raw_tts=["李奥瑞克的王冠", "先祖暗金头盔"],
            observed_fields={"name_text": "李奥瑞克的王冠", "catalog_mapped": False},
            error="Unrecognized unique",
        )
    )
    rendered = render_document(document, output_format)
    assert "stash/1/r01c01 — 李奥瑞克的王冠" in rendered
    assert "Unrecognized unique" in rendered


@pytest.mark.parametrize("locked_attempts", [1, 3])
def test_temporary_windows_replace_lock_retries_without_losing_either_snapshot(
    tmp_path, monkeypatch, locked_attempts
) -> None:
    path = tmp_path / "snapshot.json"
    temporary = path.with_suffix(".json.tmp")
    writer = SnapshotWriter(path, ExportFormat.JSON)
    document = ScanDocument("zhCN", "test")
    writer.save(document)
    old = path.read_text(encoding="utf-8")
    document.status = "complete"
    expected = render_document(document, ExportFormat.JSON)
    original_replace = Path.replace
    attempts = []
    waits = []

    def replace(source, target):
        attempts.append(target)
        assert source == temporary
        assert path.read_text(encoding="utf-8") == old
        assert temporary.read_text(encoding="utf-8") == expected
        if len(attempts) <= locked_attempts:
            raise PermissionError(13, "destination temporarily locked")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr("src.inventory_dump.exporting.sleep", waits.append)
    writer.save(document)
    assert path.read_text(encoding="utf-8") == expected
    assert not temporary.exists()
    assert attempts == [path] * (locked_attempts + 1)
    assert waits == [0.25] * locked_attempts


def test_persistent_replace_denial_is_bounded_and_keeps_old_and_pending_snapshots(tmp_path, monkeypatch) -> None:
    path = tmp_path / "snapshot.json"
    writer = SnapshotWriter(path, ExportFormat.JSON)
    document = ScanDocument("zhCN", "test")
    writer.save(document)
    old = path.read_text(encoding="utf-8")
    document.status = "complete"
    attempts = []
    waits = []

    def replace(source, target):
        attempts.append((source, target))
        raise PermissionError(13, "persistent destination lock")

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr("src.inventory_dump.exporting.sleep", waits.append)
    with pytest.raises(PermissionError, match="persistent destination lock"):
        writer.save(document)
    assert len(attempts) == 9
    assert waits == [0.25] * 8
    assert path.read_text(encoding="utf-8") == old
    assert json.loads(old)["status"] == "running"
    pending = path.with_suffix(".json.tmp").read_text(encoding="utf-8")
    assert pending == render_document(document, ExportFormat.JSON)


ADVERSARIAL = [
    "谜团",
    "```",
    "````json",
    "# 不是标题",
    "- 不是列表",
    "+12% 攻击速度",
    "<script>alert(1)</script>",
    "带 ``````` 七个反引号的文字",
    "鼠标右键",
]


def _adversarial_document() -> ScanDocument:
    document = ScanDocument("zhCN", "test", status="complete")
    document.items.append(
        ItemRecord(
            Location("stash", "1", "r01c01", (1, 1)),
            status="unparsed",
            raw_tts=list(ADVERSARIAL),
            capture_complete=True,
            observed_fields={"name_text": "谜团"},
            error="first line\nsecond line",
        )
    )
    return document


def test_markdown_raw_tts_keeps_line_breaks_inside_an_unbreakable_fence() -> None:
    markdown_it = pytest.importorskip("markdown_it")
    document = _adversarial_document()
    rendered = render_document(document, ExportFormat.MARKDOWN)
    tokens = markdown_it.MarkdownIt("commonmark").parse(rendered)
    fences = [token for token in tokens if token.type == "fence"]
    assert [token.info for token in fences] == ["text", "json"]
    assert fences[0].content == "\n".join(ADVERSARIAL) + "\n"
    assert json.loads(fences[1].content) == json.loads(json.dumps(asdict(document)))
    headings = [tokens[i + 1].content for i, token in enumerate(tokens) if token.type == "heading_open"]
    assert headings == ["D4LF 库存快照 / Inventory snapshot", "stash/1/r01c01 — 谜团"]
    # Item state renders as separate list items instead of one run-on paragraph.
    items = [tokens[i + 2].content for i, token in enumerate(tokens) if token.type == "list_item_open"]
    assert "收藏 / Favorite: unknown" in items
    assert "垃圾 / Junk: unknown" in items
    assert "原因 / Reason: first line second line" in items


def test_plain_text_keeps_raw_lines_and_unknown_states() -> None:
    rendered = render_document(_adversarial_document(), ExportFormat.TEXT)
    assert "\n".join(ADVERSARIAL) in rendered
    assert "收藏 / Favorite: unknown" in rendered
    assert "未确认是否为空的槽位 / Unverified slots: 0" in rendered
