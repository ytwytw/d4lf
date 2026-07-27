import json

from src.tools.public_safety.content_rules import content_findings


def test_detects_credentials_identity_and_personal_paths_without_echoing_values() -> None:
    private_key = "-" * 5 + "BEGIN PRIVATE " + "KEY" + "-" * 5
    github_token = "ghp_" + "a" * 36
    api_key = "sk-" + "b" * 24
    home_path = "C:" + "\\Users\\" + "account-name\\capture.json"
    real_email = "person" + "@real.example"
    payload = f"{private_key}\n{github_token}\n{api_key}\n{home_path}\n{real_email}".encode()

    findings = content_findings("notes.txt", payload)
    rules = {finding.rule for finding in findings}

    assert {"private-key", "github-token", "openai-token", "windows-home-path", "email-address"} <= rules
    assert all(github_token not in finding.detail for finding in findings)
    assert all(api_key not in finding.detail for finding in findings)
    assert all(real_email not in finding.detail for finding in findings)


def test_allows_noreply_placeholder_and_public_d2core_link() -> None:
    payload = (
        b"ytwytw@users.noreply.github.com\n"
        b"fixture@example.invalid\n"
        b"C:\\Users\\you\\code\\d4data\n"
        b"https://www.d2core.com/d4/planner?bd=20eK\n"
    )

    assert not content_findings("README.md", payload)


def test_detects_capture_manifest_outside_capture_directory() -> None:
    manifest = {
        "fingerprint": "a" * 64,
        "input": {"sha256": "b" * 64},
        "tts": {"raw_lines": ["private tooltip"], "framed_lines": []},
    }

    rules = {finding.rule for finding in content_findings("manifest.json", json.dumps(manifest).encode())}

    assert {"capture-fingerprint", "capture-artifact"} <= rules


def test_detects_binary_private_denylist_without_echoing_term() -> None:
    deny_term = "private-handle"

    findings = content_findings("metadata.bin", deny_term.encode("utf-16-le"), (deny_term,))

    assert [finding.rule for finding in findings] == ["local-denylist"]
    assert deny_term not in findings[0].detail
