from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
EXTERNAL_ACTION = re.compile(r"uses:\s*(?!\./)([^@\s]+)@([^\s#]+)")


def test_external_github_actions_are_pinned_to_full_commit_shas() -> None:
    action_files = tuple((REPO_ROOT / ".github").rglob("*.yml")) + tuple((REPO_ROOT / ".github").rglob("*.yaml"))
    uses = [
        match.groups() for path in action_files for match in EXTERNAL_ACTION.finditer(path.read_text(encoding="utf-8"))
    ]

    assert uses
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _action, revision in uses)


def test_release_workflow_keeps_zhcn_branch_version_and_commit_gates() -> None:
    release = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "branches: [zhcn-v9]" in release
    assert "github.event.pull_request.base.ref == 'zhcn-v9'" in release
    assert "github.event.pull_request.merge_commit_sha || github.sha" in release
    assert '$version -notlike "*+zhcn.*"' in release
    assert "fail_on_unmatched_files: true" in release
    assert "--require-third-party-redistribution" in ci
