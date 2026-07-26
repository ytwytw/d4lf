# Public release safety

[简体中文](public-release.zh-CN.md) | **English**

Do not change the visibility of the private development repository and do not mirror its `.git` directory. Its
custom commit authors, branch names, remote URL, reflogs, and timestamps can identify the development account.
Prepare publication in a separate Git repository built from a Git archive. Choose either an attributed fork release
that retains only the public upstream history, or an independent release with fresh history.

## Privacy boundary

The repository scanner blocks common credentials, non-placeholder email addresses, absolute home paths, private
capture fingerprints, raw JSONL, logs, recordings, screenshots in capture directories, crash/network dumps,
databases, archives, and release binaries. `.public-safety.local` adds private literal fragments without committing
or printing them. Copy `.public-safety.local.example`, then add account handles, names, emails, machine names, and
home-path fragments that must never leave the development machine.

Only the generic scanner implementation and synthetic tests are tracked so hooks and CI can enforce the same
policy. Scanner reports, SARIF output, secret baselines, discovered values, and the local denylist are ignored and
must remain outside the repository.

Only normalized, reviewed localization strings may be tracked. Raw captures, capture hashes, session UUIDs,
per-session timestamps and inventories, videos, screenshots, and replay reports remain outside Git. Aggregate,
non-identifying coverage statistics may be tracked after review. A reviewed mapping must not claim that its source
capture is publicly available.

Public build-planner URLs and their public share codes may be tracked as reproducible integration fixtures. They are
not treated as private capture data unless the linked build itself contains personal or account-identifying text.

This protects repository content and Git metadata. It cannot make publication through a personally owned GitHub
account anonymous: the account, organization membership, billing, IP records, and later interaction can still link
the publisher. A GitHub fork intentionally attributes the release to that account. Use a genuinely separate
organization or pseudonymous account, do not create a GitHub fork, and do not reuse the private repository's commit
hashes or remote when account unlinkability is required.

## Third-party data gate

The generated zhCN bundle contains data derived from Diablo4Companion, DiabloTools/d4data, and D2Core. The export
command requires `THIRD-PARTY-NOTICES.md`, the attribution policy in `docs/third-party-data.md`, source
acknowledgements in the README, and D2Core's machine-readable `documented` status. Regenerated source manifests must
retain the documented status and technical provenance.

## Attributed fork procedure

Use this procedure when the publisher accepts a public link between their GitHub account and the project. The
preparation script keeps the public upstream history through the selected V9 base, then writes exactly one squashed
release commit using the configured GitHub identity. It does not copy private development commits, branches,
reflogs, remotes, ignored files, or unreachable Git objects.

1. Configure `user.name` to the intended public GitHub name and `user.email` to a GitHub-provided
   `@users.noreply.github.com` address.

1. Populate the ignored `.public-safety.local` denylist.

1. Verify all third-party notices and the D2Core machine-readable publication status.

1. Verify README support links, `CODEOWNERS`, and release-notification workflows belong to the publishing identity;
   do not inherit upstream ownership or webhook configuration.

1. Run `uvx prek run --all-files` and the full test suite.

1. Commit the private development source and verify the worktree is clean.

1. Run
   `scripts/prepare_fork_release.ps1 -TargetPath <empty-directory-outside-this-repo> -BaseRevision v9.3.7`.

1. In the prepared directory, verify the branch, direct parent, author, clean archive content, and lack of remotes:

   ```powershell
   git status --short --branch
   git log --format=fuller -2
   git remote
   ```

1. Create the GitHub fork, add the fork remote only in the prepared directory, and push `zhcn-v9`.

The prepared repository deliberately has no remote. The publisher decides when to connect it to a GitHub fork.

## Independent release procedure

1. Populate the ignored `.public-safety.local` denylist.
1. Verify all third-party notices and the D2Core machine-readable publication status.
1. Verify README support links, `CODEOWNERS`, and release-notification workflows belong to the publishing identity;
   do not inherit upstream ownership or webhook configuration.
1. Run `uvx prek run --all-files` and the full test suite.
1. Commit the private development source and verify the worktree is clean.
1. Run `scripts/export_public_repo.ps1 -TargetPath <empty-directory-outside-this-repo>`.
1. In the exported directory, verify `git rev-list --all --count` prints `1` and `git remote` prints nothing.
1. Create an empty, non-fork GitHub repository under the intended publishing identity, then add its remote only
   from the exported directory.

The independent export script never deletes an existing target, never copies ignored files, uses a neutral author
and committer, fixes commit timestamps to UTC, and intentionally creates no remote.
