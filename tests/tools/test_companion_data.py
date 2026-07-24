import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from src.tools import companion_data

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "companion_data"


def _copy_fixture_repos(tmp_path: Path) -> tuple[Path, Path]:
    companion_repo = tmp_path / "companion"
    d4data_repo = tmp_path / "d4data"
    shutil.copytree(FIXTURE_ROOT / "companion", companion_repo)
    shutil.copytree(FIXTURE_ROOT / "d4data", d4data_repo)
    return companion_repo, d4data_repo


def _init_git_repo(repo: Path, subject: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    commands = (
        ("init", "-q"),
        ("config", "user.email", "fixture@example.invalid"),
        ("config", "user.name", "Fixture Author"),
        ("add", "."),
        ("commit", "-q", "-m", subject),
    )
    for command in commands:
        subprocess.run(["git", *command], cwd=repo, check=True, capture_output=True, env=environment)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, encoding="utf-8"
    ).stdout.strip()


def _load_joined(companion_repo: Path):
    records = companion_data.load_companion_records(companion_repo)
    entries, canonical_by_record = companion_data.join_records(records)
    return records, entries, canonical_by_record


def test_records_join_by_sno_or_internal_name_with_stable_canonical_ids(tmp_path: Path) -> None:
    companion_repo, _ = _copy_fixture_repos(tmp_path)

    records, entries, _ = _load_joined(companion_repo)
    entries_by_id = {entry.canonical_id: entry for entry in entries}

    damage = entries_by_id["affix:100"]
    assert damage.sno_aliases == ("100", "101", "102")
    assert damage.name_aliases == ("Affix_Damage", "Affix_Damage_Legacy")
    assert damage.locale_aliases == {"enUS": ("Damage",), "zhCN": ("伤害",)}

    sno_join = entries_by_id["aspect:400"]
    assert sno_join.name_aliases == ("Aspect_Chinese_Internal", "Aspect_English_Internal")
    assert sno_join.locale_aliases["zhCN"] == ("共享威能",)

    name_join = entries_by_id["aspect:410"]
    assert name_join.sno_aliases == ("410", "411")
    assert name_join.name_aliases == ("Aspect_Name_Join",)

    reversed_entries, _ = companion_data.join_records(list(reversed(records)))
    assert [entry.as_json() for entry in reversed_entries] == [entry.as_json() for entry in entries]


def test_quality_report_covers_duplicates_missing_data_and_ascii_placeholders(tmp_path: Path) -> None:
    companion_repo, _ = _copy_fixture_repos(tmp_path)
    records, entries, canonical_by_record = _load_joined(companion_repo)

    report = companion_data.build_quality_report(records, entries, canonical_by_record)

    assert report["ok"] is False
    assert report["summary"] == {
        "ascii_placeholders": 2,
        "duplicate_identity_aliases": 1,
        "duplicate_locale_aliases": 1,
        "missing_locale_aliases": 1,
        "missing_locale_records": 5,
    }
    duplicates = cast("dict[str, object]", report["duplicates"])
    identity_aliases = cast("list[dict[str, object]]", duplicates["identity_aliases"])
    locale_aliases = cast("list[dict[str, object]]", duplicates["locale_aliases"])
    missing = cast("dict[str, object]", report["missing"])
    assert identity_aliases[0]["alias"] == "200"
    assert locale_aliases[0]["canonical_ids"] == ["aspect:420", "aspect:422"]
    assert missing["locale_aliases"] == [
        {"alias_field": "Name", "canonical_id": "aspect:410", "kind": "aspect", "locale": "zhCN"}
    ]
    ascii_placeholders = cast("list[dict[str, object]]", report["ascii_placeholders"])
    assert {finding["alias"] for finding in ascii_placeholders} == {"Placeholder Aspect", "Placeholder Sword"}


def test_schema_validation_rejects_misaligned_identity_lists(tmp_path: Path) -> None:
    companion_repo, _ = _copy_fixture_repos(tmp_path)
    source_path = companion_repo / "D4Companion" / "Data" / "Affixes.enUS.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload[0]["IdNameList"] = ["Affix_Damage"]
    source_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(companion_data.SchemaValidationError, match="must have equal lengths"):
        companion_data.load_companion_records(companion_repo)


def test_loader_rejects_non_utf8_json(tmp_path: Path) -> None:
    companion_repo, _ = _copy_fixture_repos(tmp_path)
    source_path = companion_repo / "D4Companion" / "Data" / "Affixes.enUS.json"
    source_path.write_bytes(b"\xff")

    with pytest.raises(companion_data.CompanionDataError, match="is not valid UTF-8"):
        companion_data.load_companion_records(companion_repo)


def test_cli_writes_reproducible_outputs_and_source_metadata_to_requested_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    companion_repo, d4data_repo = _copy_fixture_repos(tmp_path)
    companion_commit = _init_git_repo(companion_repo, "Fixture companion data")
    d4data_commit = _init_git_repo(d4data_repo, "Rebuilt JSON 9.8.7.65432")
    first_output = tmp_path / "requested" / "first"
    second_output = tmp_path / "requested" / "second"
    common_args = ["--companion-repo", str(companion_repo), "--d4data-repo", str(d4data_repo)]

    assert companion_data.main([*common_args, "--output-dir", str(first_output)]) == 1
    assert companion_data.main([*common_args, "--output-dir", str(second_output)]) == 1
    capsys.readouterr()

    first_manifest = first_output / companion_data.MANIFEST_FILENAME
    second_manifest = second_output / companion_data.MANIFEST_FILENAME
    first_quality = first_output / companion_data.QUALITY_REPORT_FILENAME
    second_quality = second_output / companion_data.QUALITY_REPORT_FILENAME
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert first_quality.read_bytes() == second_quality.read_bytes()

    manifest_text = first_manifest.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert str(tmp_path) not in manifest_text
    assert manifest["sources"]["diablo4_companion"]["app_version"] == "9.8.7.0"
    assert manifest["sources"]["diablo4_companion"]["data_build"] is None
    assert manifest["sources"]["diablo4_companion"]["commit"] == companion_commit
    assert manifest["sources"]["d4data"]["build"] == "9.8.7.65432"
    assert manifest["sources"]["d4data"]["build_commit"] == d4data_commit
    assert manifest["sources"]["d4data"]["commit"] == d4data_commit
    assert set(manifest["sources"]["diablo4_companion"]["files"]) == {
        f"D4Companion/Data/{spec.filename_stem}.{locale}.json"
        for spec in companion_data.DATASET_SPECS
        for locale in companion_data.LOCALES
    }
    assert all(not Path(source_file).is_absolute() for source_file in manifest["sources"]["diablo4_companion"]["files"])


def test_companion_data_build_ignores_application_version_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    log = "app-commit\tv5.3.4.0\ndata-commit\tUpdated data for v3.1.0.72592"
    monkeypatch.setattr(companion_data, "_run_git", lambda *_args, **_kwargs: log)

    assert companion_data._companion_data_build(Path("unused")) == ("3.1.0.72592", "data-commit")
