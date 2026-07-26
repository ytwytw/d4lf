import json
from pathlib import Path

from src.tools.documentation_check import check_documentation

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _write_pair(tmp_path: Path, en_text: str, zh_text: str) -> Path:
    (tmp_path / "guide.md").write_text(en_text, encoding="utf-8")
    (tmp_path / "guide.zh-CN.md").write_text(zh_text, encoding="utf-8")
    manifest = tmp_path / "pairs.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "pairs": [{"en": "guide.md", "zh_CN": "guide.zh-CN.md"}]}), encoding="utf-8"
    )
    return manifest


def test_repository_documentation_is_fully_paired() -> None:
    assert check_documentation(REPOSITORY_ROOT) == []


def test_matching_pair_passes(tmp_path: Path) -> None:
    manifest = _write_pair(
        tmp_path,
        (
            "# Guide_name\n\n[简体中文](guide.zh-CN.md) | **English**\n\n"
            "[Section](#guide_name)\n\n[Source](https://example.com/source)\n"
        ),
        (
            "# Guide_name\n\n**简体中文** | [English](guide.md)\n\n"
            "[章节](#guide_name)\n\n[来源](https://example.com/source)\n"
        ),
    )

    findings = check_documentation(tmp_path, manifest, markdown_paths={"guide.md", "guide.zh-CN.md"})

    assert findings == []


def test_external_url_drift_is_rejected(tmp_path: Path) -> None:
    manifest = _write_pair(
        tmp_path,
        "# Guide\n\n[简体中文](guide.zh-CN.md) | **English**\n\n[Source](https://example.com/en)\n",
        "# 指南\n\n**简体中文** | [English](guide.md)\n\n[来源](https://example.com/zh)\n",
    )

    findings = check_documentation(tmp_path, manifest, markdown_paths={"guide.md", "guide.zh-CN.md"})

    assert "external_url_mismatch" in {finding.code for finding in findings}


def test_missing_counterpart_and_anchor_are_rejected(tmp_path: Path) -> None:
    manifest = _write_pair(
        tmp_path,
        "# Guide\n\n[简体中文](guide.zh-CN.md) | **English**\n\n[Missing](#missing)\n",
        "# 指南\n\n**简体中文** | [English](guide.md)\n\n[缺失](#missing)\n",
    )

    findings = check_documentation(tmp_path, manifest, markdown_paths={"guide.md", "guide.zh-CN.md", "orphan.md"})
    codes = {finding.code for finding in findings}

    assert "missing_anchor" in codes
    assert "unpaired_document" in codes


def test_duplicate_anchor_and_code_drift_are_rejected(tmp_path: Path) -> None:
    manifest = _write_pair(
        tmp_path,
        (
            "# Guide\n\n[简体中文](guide.zh-CN.md) | **English**\n\n"
            '<a id="same"></a>\n<a id="same"></a>\n\n```text\nstable\n```\n'
        ),
        "# 指南\n\n**简体中文** | [English](guide.md)\n\n```text\nchanged\n```\n",
    )

    findings = check_documentation(tmp_path, manifest, markdown_paths={"guide.md", "guide.zh-CN.md"})
    codes = {finding.code for finding in findings}

    assert "code_block_mismatch" in codes
    assert "duplicate_anchor" in codes


def test_untranslated_chinese_stub_is_rejected(tmp_path: Path) -> None:
    english_prose = " ".join(["documentation"] * 100)
    manifest = _write_pair(
        tmp_path,
        f"# Guide\n\n[简体中文](guide.zh-CN.md) | **English**\n\n{english_prose}\n",
        f"# Guide\n\n**简体中文** | [English](guide.md)\n\n{english_prose}\n",
    )

    findings = check_documentation(tmp_path, manifest, markdown_paths={"guide.md", "guide.zh-CN.md"})

    assert "insufficient_chinese_text" in {finding.code for finding in findings}


def test_inline_machine_and_ui_label_drift_are_rejected(tmp_path: Path) -> None:
    i18n_path = tmp_path / "src/gui/i18n.py"
    i18n_path.parent.mkdir(parents=True)
    i18n_path.write_text('_ZH_CN_TEXT = {"Stop and Save": "结束并保存"}\n', encoding="utf-8")
    manifest = _write_pair(
        tmp_path,
        ("# Guide\n\n[简体中文](guide.zh-CN.md) | **English**\n\nChoose **Stop and Save** and use `rarity: rare`.\n"),
        "# 指南\n\n**简体中文** | [English](guide.md)\n\n选择**停止并保存**并使用 `rarity: common`。\n",
    )

    findings = check_documentation(tmp_path, manifest, markdown_paths={"guide.md", "guide.zh-CN.md"})

    assert "protected_term_mismatch" in {finding.code for finding in findings}
    assert any(finding.path == "guide.md" and finding.line == 5 for finding in findings)
