from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from src.locale_data import LocaleGrammar
from src.tools import d2core_data, generate_zhcn_assets, locale_data_check

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "companion_data"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()


def _d2core_snapshot(tmp_path: Path, build_version: str = "65432") -> Path:
    root = tmp_path / "d2core"
    payloads = {
        ("affix", "enUS"): _json_bytes({"affix": [{"key": "Affix_Damage", "id": 100, "descTpl": "+[{VALUE}] Damage"}]}),
        ("affix", "zhCN"): _json_bytes({
            "affix": [{"key": "Affix_Damage", "id": 100, "descTpl": "+[{VALUE}] 暗核伤害"}]
        }),
        ("aspect", "enUS"): _json_bytes([{"key": "Aspect_Shared", "id": 400, "name": "Shared Aspect"}]),
        ("aspect", "zhCN"): _json_bytes([{"key": "Aspect_Shared", "id": 400, "name": "暗核共享之威能"}]),
        ("uniqueItem", "enUS"): _json_bytes([{"key": "Unique_Known", "id": 500, "name": "Known Unique"}]),
        ("uniqueItem", "zhCN"): _json_bytes([{"key": "Unique_Known", "id": 500, "name": "暗核暗金"}]),
        ("talisman", "enUS"): _json_bytes({
            "charm": [],
            "seal": [{"key": "Seal_Test", "id": 600, "name": "Seal of Test"}],
            "itemSets": {"Talisman_Test": {"id": 601, "name": "Missing Set"}},
            "affixes": {
                "charm": [{"key": "Charm_Affix", "id": 602, "descTpl": "+[{VALUE}] Test Charm Damage"}],
                "seal": [{"key": "Seal_Affix", "id": 603, "descTpl": "+[{VALUE}] Test Seal Damage"}],
            },
        }),
        ("talisman", "zhCN"): _json_bytes({
            "charm": [],
            "seal": [{"key": "Seal_Test", "id": 600, "name": "测试封印"}],
            "itemSets": {"Talisman_Test": {"id": 601, "name": "暗核套装"}},
            "affixes": {
                "charm": [{"key": "Charm_Affix", "id": 602, "descTpl": "+[{VALUE}] 暗核神符伤害"}],
                "seal": [{"key": "Seal_Affix", "id": 603, "descTpl": "+[{VALUE}] 暗核封印伤害"}],
            },
        }),
    }
    records = {key: d2core_data.validate_dataset_payload(*key, payload) for key, payload in payloads.items()}
    urls = {key: d2core_data.dataset_url(build_version, *key) for key in payloads}
    manifest = d2core_data.build_manifest(
        build_version=build_version,
        payloads=payloads,
        records=records,
        urls=urls,
        build_version_source={"kind": "pinned"},
    )
    d2core_data.write_snapshot(root, manifest, payloads)
    return root


def _init_git_repo(repo: Path, subject: str) -> None:
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    for command in (
        ("init", "-q"),
        ("config", "user.email", "fixture@example.invalid"),
        ("config", "user.name", "Fixture Author"),
        ("add", "."),
        ("commit", "-q", "-m", subject),
    ):
        subprocess.run(["git", *command], cwd=repo, check=True, capture_output=True, env=environment)


def _fixture_repos(tmp_path: Path) -> tuple[Path, Path]:
    companion_repo = tmp_path / "companion"
    d4data_repo = tmp_path / "d4data"
    shutil.copytree(FIXTURE_ROOT / "companion", companion_repo)
    shutil.copytree(FIXTURE_ROOT / "d4data", d4data_repo)
    data_dir = companion_repo / "D4Companion" / "Data"
    _write_json(
        data_dir / "ItemTypes.enUS.json",
        [
            {"Name": "Common Amulet", "Rarerity": "Normal", "Type": "amulet"},
            {"Name": "Ancestral Common Amulet", "Rarerity": "Normal", "Type": "amulet"},
            {"Name": "Nightmare Sigil", "Rarerity": "", "Type": "sigil"},
        ],
    )
    _write_json(
        data_dir / "ItemTypes.zhCN.json",
        [
            {"Name": "\u666e\u901a\u62a4\u7b26", "Rarerity": "Normal", "Type": "amulet"},
            {"Name": "\u5148\u7956\u666e\u901a\u62a4\u7b26", "Rarerity": "Normal", "Type": "amulet"},
            {"Name": "\u68a6\u9b47\u7b26\u5370", "Rarerity": "", "Type": "sigil"},
        ],
    )
    sigil_common = {
        "IdSno": 700,
        "IdName": "World_DGN_Test",
        "Description": "",
        "DungeonZoneInfo": "",
        "IsSeasonal": False,
        "Type": "Dungeon",
    }
    _write_json(data_dir / "Sigils.enUS.json", [{**sigil_common, "Name": "Test Dungeon"}])
    _write_json(data_dir / "Sigils.zhCN.json", [{**sigil_common, "Name": "测试地下城"}])
    (d4data_repo / "buildVersion.txt").write_text("9.8.7.65432\n", encoding="utf-8")
    _init_git_repo(companion_repo, "Updated data for v9.8.7.65432")
    _init_git_repo(d4data_repo, "Rebuilt JSON 9.8.7.65432")
    return companion_repo, d4data_repo


def _language_assets(tmp_path: Path) -> tuple[Path, Path]:
    en_us_dir = tmp_path / "enUS"
    en_us_dir.mkdir()
    _write_json(en_us_dir / "affixes.json", {"damage": "Damage"})
    _write_json(en_us_dir / "charms_affixes.json", {})
    _write_json(en_us_dir / "seals_affixes.json", {})
    _write_json(en_us_dir / "aspects.json", ["shared_aspect"])
    _write_json(en_us_dir / "sets.json", ["missing_set"])
    _write_json(en_us_dir / "uniques.json", {"known_unique": {"num_inherents": 0}})
    _write_json(
        en_us_dir / "sigils.json",
        {"dungeons": {"test_dungeon": "test dungeon"}, "major": {}, "minor": {}, "positive": {}, "rarities": {}},
    )
    _write_json(en_us_dir / "tributes.json", {"missing_tribute": "missing tribute"})
    _write_json(
        en_us_dir / "item_types.json",
        {"Amulet": "amulet", "Elixir": "elixir", "Sigil": "custom type sigil", "Tome": "tome"},
    )
    _write_json(en_us_dir / "tooltips.json", {"ItemPower": "item power"})
    _write_json(en_us_dir / "corrections.json", {})
    _write_json(
        en_us_dir / "grammar.json",
        {
            "schema_version": 1,
            "labels": {"item_power": ["item power"]},
            "identifiers": {},
            "rarities": {"Common": ["common"]},
        },
    )
    zhcn_grammar = tmp_path / "grammar.zhCN.json"
    _write_json(
        zhcn_grammar,
        {
            "schema_version": 1,
            "labels": {"item_power": ["物品强度"]},
            "identifiers": {},
            "rarities": {"Common": ["普通"]},
        },
    )
    return en_us_dir, zhcn_grammar


def test_generator_keeps_stable_keys_and_reports_unresolved_without_english_fallback(tmp_path: Path) -> None:
    companion_repo, d4data_repo = _fixture_repos(tmp_path)
    en_us_dir, zhcn_grammar = _language_assets(tmp_path)
    output_dir = tmp_path / "first" / "lang" / "zhCN"
    catalog_dir = tmp_path / "first" / "catalog"

    bundle = generate_zhcn_assets.generate_zhcn_assets(
        companion_repo=companion_repo,
        d4data_repo=d4data_repo,
        en_us_dir=en_us_dir,
        zhcn_grammar=zhcn_grammar,
        output_dir=output_dir,
        catalog_dir=catalog_dir,
    )

    assert json.loads((output_dir / "affixes.json").read_text(encoding="utf-8")) == {"damage": "伤害"}
    assert json.loads((output_dir / "aspects.json").read_text(encoding="utf-8")) == {"shared_aspect": "共享威能"}
    uniques = json.loads((output_dir / "uniques.json").read_text(encoding="utf-8"))
    assert uniques["known_unique"]["display_name"] == "知名暗金"
    assert json.loads((output_dir / "item_types.json").read_text(encoding="utf-8")) == {
        "Amulet": "\u62a4\u7b26",
        "Elixir": "",
        "Sigil": "\u68a6\u9b47\u7b26\u5370",
        "Tome": "",
    }
    assert json.loads((output_dir / "sigils.json").read_text(encoding="utf-8"))["dungeons"] == {
        "test_dungeon": "测试地下城"
    }
    assert json.loads((output_dir / "sets.json").read_text(encoding="utf-8")) == {"missing_set": ""}
    assert json.loads((output_dir / "tributes.json").read_text(encoding="utf-8")) == {"missing_tribute": ""}

    quality = cast("dict[str, object]", json.loads(bundle.quality_report.read_text(encoding="utf-8")))
    scope = cast("dict[str, object]", quality["scope"])
    summary = cast("dict[str, object]", quality["summary"])
    assert quality["runtime_ready"] is False
    assert scope["excluded_item_types"] == ["Elixir", "Tome"]
    assert summary["excluded_records"] == 2
    unresolved_items = cast("list[dict[str, object]]", quality["unresolved"])
    unresolved = {issue["stable_id"] for issue in unresolved_items}
    assert unresolved == {"sets:missing_set", "tributes:missing_tribute"}
    assert "missing set" not in (output_dir / "sets.json").read_text(encoding="utf-8")

    report = locale_data_check.check_locale_data(
        source_lock=bundle.source_lock,
        build_version=catalog_dir / "d4data-buildVersion.txt",
        locale_manifest=bundle.locale_manifest,
    )
    assert report["exit_code"] == locale_data_check.EXIT_CHECK_FAILED
    report_summary = cast("dict[str, object]", report["summary"])
    assert report_summary["issue_counts"] == {"missing_record": 2}


def test_generator_is_deterministic_and_cli_fails_closed_by_default(tmp_path: Path) -> None:
    companion_repo, d4data_repo = _fixture_repos(tmp_path)
    en_us_dir, zhcn_grammar = _language_assets(tmp_path)
    roots = [tmp_path / "first", tmp_path / "second"]
    common_args = [
        "--companion-repo",
        str(companion_repo),
        "--d4data-repo",
        str(d4data_repo),
        "--en-us-dir",
        str(en_us_dir),
        "--zhcn-grammar",
        str(zhcn_grammar),
    ]

    assert (
        generate_zhcn_assets.main([
            *common_args,
            "--output-dir",
            str(roots[0] / "lang" / "zhCN"),
            "--catalog-dir",
            str(roots[0] / "catalog"),
        ])
        == 1
    )
    assert (
        generate_zhcn_assets.main([
            *common_args,
            "--output-dir",
            str(roots[1] / "lang" / "zhCN"),
            "--catalog-dir",
            str(roots[1] / "catalog"),
            "--allow-unresolved",
        ])
        == 0
    )

    first_files = {path.relative_to(roots[0]): path.read_bytes() for path in roots[0].rglob("*") if path.is_file()}
    second_files = {path.relative_to(roots[1]): path.read_bytes() for path in roots[1].rglob("*") if path.is_file()}
    assert first_files == second_files


def test_generator_applies_and_tracks_publishable_reviewed_overrides(tmp_path: Path) -> None:
    companion_repo, d4data_repo = _fixture_repos(tmp_path)
    en_us_dir, zhcn_grammar = _language_assets(tmp_path)
    output_dir = tmp_path / "output" / "lang" / "zhCN"
    catalog_dir = tmp_path / "output" / "catalog"
    overrides = tmp_path / "reviewed_zhCN.json"
    _write_json(
        overrides,
        {
            "schema_version": 1,
            "locale": "zhCN",
            "records": {
                "affixes:damage": "实测伤害",
                "sets:missing_set": "实测套装",
                "tributes:missing_tribute": "实测贡品",
            },
        },
    )

    bundle = generate_zhcn_assets.generate_zhcn_assets(
        companion_repo=companion_repo,
        d4data_repo=d4data_repo,
        en_us_dir=en_us_dir,
        zhcn_grammar=zhcn_grammar,
        output_dir=output_dir,
        catalog_dir=catalog_dir,
        reviewed_overrides=overrides,
    )

    assert json.loads((output_dir / "affixes.json").read_text(encoding="utf-8"))["damage"] == "实测伤害"
    quality = json.loads(bundle.quality_report.read_text(encoding="utf-8"))
    assert quality["summary"]["reviewed_overrides"] == 3
    assert quality["unresolved"] == []
    manifest = json.loads(bundle.locale_manifest.read_text(encoding="utf-8"))
    assert manifest["reviewed_overrides"] == {
        "path": overrides.name,
        "sha256": hashlib.sha256(overrides.read_bytes()).hexdigest(),
    }


def test_generator_rejects_private_evidence_in_reviewed_overrides(tmp_path: Path) -> None:
    overrides = tmp_path / "reviewed_zhCN.json"
    _write_json(
        overrides,
        {
            "schema_version": 1,
            "locale": "zhCN",
            "evidence": [{"record_count": 1}],
            "records": {"affixes:damage": "测试伤害"},
        },
    )

    with pytest.raises(generate_zhcn_assets.GenerationError, match="must not contain private capture evidence"):
        generate_zhcn_assets._reviewed_overrides(overrides)


def test_companion_records_take_precedence_and_d2core_supplements_missing_translations(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(d2core_data, "MINIMUM_RECORD_COUNTS", {spec.name: 1 for spec in d2core_data.DATASET_SPECS})
    companion_repo, d4data_repo = _fixture_repos(tmp_path)
    en_us_dir, zhcn_grammar = _language_assets(tmp_path)
    _write_json(en_us_dir / "charms_affixes.json", {"test_charm_damage": "test charm damage"})
    _write_json(en_us_dir / "seals_affixes.json", {"test_seal_damage": "test seal damage"})
    _write_json(en_us_dir / "aspects.json", ["shared_aspect", "retired_aspect"])
    _write_json(
        en_us_dir / "uniques.json", {"known_unique": {"num_inherents": 0}, "seal_of_test": {"num_inherents": 0}}
    )
    output_dir = tmp_path / "output" / "lang" / "zhCN"
    catalog_dir = tmp_path / "output" / "catalog"
    overrides = tmp_path / "reviewed_zhCN.json"
    _write_json(overrides, {"schema_version": 1, "locale": "zhCN", "records": {"tributes:missing_tribute": "测试贡品"}})

    bundle = generate_zhcn_assets.generate_zhcn_assets(
        companion_repo=companion_repo,
        d4data_repo=d4data_repo,
        en_us_dir=en_us_dir,
        zhcn_grammar=zhcn_grammar,
        output_dir=output_dir,
        catalog_dir=catalog_dir,
        d2core_dir=_d2core_snapshot(tmp_path),
        reviewed_overrides=overrides,
    )

    assert json.loads((output_dir / "affixes.json").read_text(encoding="utf-8"))["damage"] == "伤害"
    generated_aspects = json.loads((output_dir / "aspects.json").read_text(encoding="utf-8"))
    assert generated_aspects == {"retired_aspect": "", "shared_aspect": "共享威能"}
    uniques = json.loads((output_dir / "uniques.json").read_text(encoding="utf-8"))
    assert uniques["known_unique"]["display_name"] == "知名暗金"
    assert uniques["seal_of_test"]["display_name"] == "测试封印"
    assert json.loads((output_dir / "charms_affixes.json").read_text(encoding="utf-8")) == {
        "test_charm_damage": "暗核神符伤害"
    }
    assert json.loads((output_dir / "seals_affixes.json").read_text(encoding="utf-8")) == {
        "test_seal_damage": "暗核封印伤害"
    }
    assert json.loads((output_dir / "sets.json").read_text(encoding="utf-8")) == {"missing_set": "暗核套装"}

    manifest = json.loads(bundle.locale_manifest.read_text(encoding="utf-8"))
    records = {record["stable_id"]: record for record in manifest["records"]}
    for stable_id in (
        "charms_affixes:test_charm_damage",
        "seals_affixes:test_seal_damage",
        "sets:missing_set",
        "uniques:seal_of_test",
    ):
        source = records[stable_id]["translation_source"]
        assert source["provider"] == "d2core"
        assert source["source_id"]
        assert len(source["source_record_sha256"]) == 64
        assert len(source["translation_sha256"]) == 64

    source_manifest = json.loads((catalog_dir / "source-manifest.json").read_text(encoding="utf-8"))
    assert source_manifest["sources"]["d2core"]["authorization"] == {
        "public_redistribution": "documented",
        "reference": "docs/third-party-data.md#d2core",
    }
    d2core_index = source_manifest["sources"]["d2core"]["translation_record_index"]
    charm_source = records["charms_affixes:test_charm_damage"]["translation_source"]
    assert d2core_index[charm_source["source_id"]] == {
        "source_record_sha256": charm_source["source_record_sha256"],
        "translation_sha256": charm_source["translation_sha256"],
    }
    quality = json.loads(bundle.quality_report.read_text(encoding="utf-8"))
    assert quality["summary"]["source_builds_match"] is True
    assert quality["summary"]["translation_conflicts"] == 3
    assert quality["summary"]["translation_sources"]["d2core"] == 4
    assert quality["summary"]["unresolved_records"] == 1
    assert quality["summary"]["excluded_historical_records"] == 0
    assert quality["scope"]["excluded_historical_records"] == []
    assert quality["runtime_ready"] is False

    release_report = locale_data_check.check_locale_data(
        source_lock=bundle.source_lock,
        build_version=catalog_dir / "d4data-buildVersion.txt",
        locale_manifest=bundle.locale_manifest,
    )
    release_issues = cast("list[dict[str, object]]", release_report["issues"])
    assert {issue["code"] for issue in release_issues} == {
        "missing_record",
        "runtime_not_ready",
        "translation_conflict",
    }


def test_d2core_duplicate_identities_are_order_independent_or_rejected(tmp_path: Path) -> None:
    def snapshot(en_us: tuple[dict[str, object], ...], zh_cn: tuple[dict[str, object], ...]):
        return d2core_data.D2CoreSnapshot(
            root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            build_version="65432",
            manifest={},
            payloads={},
            records={("affix", "enUS"): en_us, ("affix", "zhCN"): zh_cn},
        )

    english: tuple[dict[str, object], ...] = (
        {"key": "Duplicate", "id": 1, "descTpl": "+[{VALUE}] Damage", "group": "first"},
        {"key": "Duplicate", "id": 1, "descTpl": "+[{VALUE}] Damage", "group": "second"},
    )
    chinese: tuple[dict[str, object], ...] = (
        {"key": "Duplicate", "id": 1, "descTpl": "+[{VALUE}] 伤害", "group": "second"},
        {"key": "Duplicate", "id": 1, "descTpl": "+[{VALUE}] 伤害", "group": "first"},
    )

    pairs = generate_zhcn_assets._paired_d2core_records(snapshot(english, chinese), "affix")
    assert len(pairs) == 1
    assert pairs[0][2] == 2

    ambiguous: tuple[dict[str, object], ...] = (
        english[0],
        {"key": "Duplicate", "id": 1, "descTpl": "+[{VALUE}] Armor"},
    )
    with pytest.raises(generate_zhcn_assets.GenerationError, match="ambiguous localized records"):
        generate_zhcn_assets._paired_d2core_records(snapshot(ambiguous, chinese), "affix")


def test_translation_provider_absence_never_excludes_a_companion_translation() -> None:
    builder = generate_zhcn_assets._BundleBuilder()

    translation = builder.resolve("aspects:retired_aspect", "retired aspect", {"旧版威能"})

    assert translation == "旧版威能"
    assert builder.source_records == {
        "aspects:retired_aspect": {
            "source_sha256": hashlib.sha256(b"retired aspect").hexdigest(),
            "stable_id": "aspects:retired_aspect",
            "text": "retired aspect",
        }
    }
    assert builder.locale_records == {
        "aspects:retired_aspect": {
            "source_sha256": hashlib.sha256(b"retired aspect").hexdigest(),
            "stable_id": "aspects:retired_aspect",
            "text": "旧版威能",
            "translation_source": {
                "provider": "diablo4_companion",
                "source_id": "aspects:retired_aspect",
                "translation_sha256": hashlib.sha256("旧版威能".encode()).hexdigest(),
            },
        }
    }
    assert builder.unresolved == []
    assert builder.excluded_historical == []


def test_flat_stat_candidate_takes_precedence_over_percent_variant() -> None:
    flat = generate_zhcn_assets._TranslationCandidate(
        text="点敏捷", provider="d2core", source_id="affix:S04_CoreStat_Dexterity:1:x1", source_record_sha256="1" * 64
    )
    percent = generate_zhcn_assets._TranslationCandidate(
        text="敏捷",
        provider="d2core",
        source_id="affix:S04_CoreStat_DexterityPercent:2:x1",
        source_record_sha256="2" * 64,
    )
    index = {generate_zhcn_assets._identity("dexterity"): {flat, percent}}

    assert generate_zhcn_assets._preferred_candidate_values(index, "dexterity", "dexterity") == {flat}


def test_selected_alias_collisions_are_reported_by_runtime_namespace() -> None:
    collisions = generate_zhcn_assets._selected_alias_collisions({
        "aspects": [("malicious", "恶毒"), ("virulent", "恶毒")],
        "uniques": [("first", "第一件"), ("second", "第二件")],
    })

    assert collisions == [
        {"namespace": "aspects", "normalized_alias": "恶毒", "stable_ids": ["malicious", "virulent"], "texts": ["恶毒"]}
    ]


def test_affix_collision_is_only_accepted_when_range_rule_exactly_covers_it() -> None:
    collision: dict[str, object] = {
        "namespace": "affixes",
        "normalized_alias": "暗影伤害",
        "stable_ids": ["shade_damage", "shadow_damage"],
        "texts": ["暗影伤害"],
    }
    grammar = LocaleGrammar.from_dict(
        "zhCN", {"affix_range_precision": {"暗影伤害": {"decimal": "shade_damage", "integer": "shadow_damage"}}}
    )

    unresolved, disambiguated = generate_zhcn_assets._partition_disambiguated_alias_collisions([collision], grammar)

    assert unresolved == []
    assert disambiguated == [
        {**collision, "strategy": "range_precision", "mapping": {"decimal": "shade_damage", "integer": "shadow_damage"}}
    ]

    incomplete = LocaleGrammar.from_dict("zhCN", {"affix_range_precision": {"暗影伤害": {"decimal": "shade_damage"}}})
    assert generate_zhcn_assets._partition_disambiguated_alias_collisions([collision], incomplete) == ([collision], [])


def test_aspect_collision_is_only_accepted_when_declared_as_an_equivalent_group() -> None:
    collision: dict[str, object] = {
        "namespace": "aspects",
        "normalized_alias": "恶毒",
        "stable_ids": ["malicious", "virulent"],
        "texts": ["恶毒"],
    }
    grammar = LocaleGrammar.from_dict("zhCN", {"aspect_alias_equivalence": {"恶毒": ["malicious", "virulent"]}})

    unresolved, disambiguated = generate_zhcn_assets._partition_disambiguated_alias_collisions([collision], grammar)

    assert unresolved == []
    assert disambiguated == [
        {**collision, "strategy": "equivalent_canonical_ids", "canonical_ids": ["malicious", "virulent"]}
    ]

    incomplete = LocaleGrammar.from_dict("zhCN", {"aspect_alias_equivalence": {"恶毒": ["malicious"]}})
    assert generate_zhcn_assets._partition_disambiguated_alias_collisions([collision], incomplete) == ([collision], [])
