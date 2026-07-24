from __future__ import annotations

import json

from src.tools.public_safety import scan_items, third_party_redistribution_findings


def _rules(items: dict[str, bytes], deny_terms: tuple[str, ...] = ()) -> set[str]:
    return {finding.rule for finding in scan_items(items, deny_terms)}


def _third_party_items(*, d2core_status: str = "documented") -> dict[str, bytes]:
    manifest = {
        "sources": {
            "d2core": {
                "authorization": {
                    "public_redistribution": d2core_status,
                    "reference": "docs/third-party-data.md#d2core",
                }
            },
            "d4data": {"repository": "https://github.com/DiabloTools/d4data.git"},
            "diablo4_companion": {"repository": "https://github.com/josdemmers/Diablo4Companion.git"},
        }
    }
    policy = (
        "# Third-party data\n\n"
        f"## D2Core\n\nPublic redistribution status: {d2core_status}.\n\n"
        "## Diablo4Companion\n\nMIT License.\n\n"
        "## DiabloTools/d4data\n\nMIT License.\n"
    )
    readme = (
        "D2Core data source: https://www.d2core.com/\n"
        "Diablo4Companion: https://github.com/josdemmers/Diablo4Companion\n"
        "DiabloTools/d4data: https://github.com/DiabloTools/d4data\n"
    )
    notices = (
        "# Third-party notices\n\n"
        "## Diablo4Companion\n"
        "https://github.com/josdemmers/Diablo4Companion\n"
        "Copyright (c) 2022 Jos Demmers\n"
        "Permission is hereby granted\n\n"
        "## DiabloTools/d4data\n"
        "https://github.com/DiabloTools/d4data\n"
        "Copyright (c) 2023 blizzhackers\n"
        "Permission is hereby granted\n"
    )
    return {
        "assets/catalog/source-manifest.json": json.dumps(manifest).encode(),
        "docs/third-party-data.md": policy.encode(),
        "README.md": readme.encode(),
        "THIRD-PARTY-NOTICES.md": notices.encode(),
    }


def test_scan_rejects_private_paths_and_capture_artifacts() -> None:
    items = {
        ".env": b"TOKEN=placeholder\n",
        "captures/session.jsonl": b"{}\n",
        "recordings/tooltip.mp4": b"video",
        "tests/assets/example.png": b"public fixture",
        ".env.example": b"TOKEN=\n",
        "forced.log": b"private run log\n",
        "secret-scan.sarif": b"{}\n",
        "settings.bak": b"backup\n",
    }

    rules = _rules(items)

    assert "sensitive-filename" in rules
    assert "private-data-directory" in rules
    assert "sensitive-file-type" in rules
    assert all(finding.path != "tests/assets/example.png" for finding in scan_items(items))
    assert all(finding.path != ".env.example" for finding in scan_items(items))


def test_scan_detects_replay_and_automatic_capture_json_outside_capture_directories() -> None:
    replay_report = {"input": {"sha256": "a" * 64}}
    automatic_manifest = {
        "fingerprint": "b" * 64,
        "tts": {"raw_lines": ["private tooltip"], "framed_lines": ["private tooltip"]},
    }

    rules = _rules({
        "replay.json": json.dumps(replay_report).encode(),
        "manifest.json": json.dumps(automatic_manifest).encode(),
    })

    assert {"capture-fingerprint", "capture-artifact"} <= rules


def test_scan_detects_high_confidence_secrets_without_echoing_values() -> None:
    private_key = "-" * 5 + "BEGIN PRIVATE " + "KEY" + "-" * 5
    github_token = "ghp_" + "a" * 36
    home_path = "C:" + "\\Users\\" + "account-name\\capture.json"
    real_email = "person" + "@real.example"
    capture_digest = '"input_' + 'sha256": "abc"'
    payload = f"{private_key}\n{github_token}\n{home_path}\n{real_email}\n{capture_digest}".encode()

    findings = scan_items({"notes.txt": payload})
    rules = {finding.rule for finding in findings}

    assert {"private-key", "github-token", "windows-home-path", "email-address", "capture-fingerprint"} <= rules
    assert all(github_token not in finding.detail for finding in findings)
    assert all(real_email not in finding.detail for finding in findings)


def test_scan_allows_placeholder_email_and_checks_binary_denylist() -> None:
    assert not scan_items({
        "fixture.txt": b"fixture@example.invalid\n",
        "public-identity.txt": b"publisher@users.noreply.github.com\n",
    })

    deny_term = "private-handle"
    findings = scan_items({"metadata.bin": deny_term.encode("utf-16-le")}, (deny_term,))

    assert [finding.rule for finding in findings] == ["local-denylist"]
    assert deny_term not in findings[0].detail


def test_third_party_gate_fails_closed_until_redistribution_is_documented() -> None:
    items = _third_party_items(d2core_status="unverified")

    findings = third_party_redistribution_findings(items)

    assert len(findings) == 1
    assert findings[0].rule == "third-party-license"

    items = _third_party_items()
    assert not third_party_redistribution_findings(items)

    items["README.md"] = b"No source attribution.\n"
    findings = third_party_redistribution_findings(items)
    assert len(findings) == 3
    assert {finding.path for finding in findings} == {"README.md"}


def test_third_party_gate_requires_mit_data_source_notices() -> None:
    items = _third_party_items()
    items["THIRD-PARTY-NOTICES.md"] = b"Incomplete notices.\n"

    findings = third_party_redistribution_findings(items)

    assert len(findings) == 2
    assert {finding.path for finding in findings} == {"THIRD-PARTY-NOTICES.md"}


def test_third_party_gate_requires_mit_source_provenance() -> None:
    items = _third_party_items()
    manifest = json.loads(items["assets/catalog/source-manifest.json"])
    del manifest["sources"]["diablo4_companion"]
    items["assets/catalog/source-manifest.json"] = json.dumps(manifest).encode()

    findings = third_party_redistribution_findings(items)

    assert len(findings) == 1
    assert findings[0].path == "assets/catalog/source-manifest.json"


def test_third_party_gate_fails_when_manifest_or_d2core_metadata_is_missing() -> None:
    assert third_party_redistribution_findings({})
    assert third_party_redistribution_findings({"assets/catalog/source-manifest.json": b'{"sources": {}}'})
