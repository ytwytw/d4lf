# Locale data update checks

`src.tools.locale_data_check` is the fail-closed gate for generated locale data. Run it after generating a
locale and before reviewing or committing generated files. It does not modify the source checkout or generated
assets.

## Generate the zhCN candidate

Use full Companion and d4data checkouts plus a validated D2Core snapshot. The snapshot command discovers the
current D2Core build, downloads only the paired affix/aspect/Unique/Talisman static JSON, verifies every `(key, id)`
pair, enforces equal locale counts and conservative per-dataset record floors, and writes exact source hashes. The
current floors are 750 affixes, 250 aspects, 200 unique items, and 500 flattened Talisman records per locale. A
legitimate source contraction therefore requires an explicit policy review instead of silently retiring equipment.
The command does not access the planner or the game client.

```powershell
uv run python -m src.tools.d2core_data `
    --output-dir C:\temp\d4lf-d2core
```

Generate into a temporary directory first; `--allow-unresolved` permits diagnostic output but does not set
`runtime_ready` or weaken the release checker.

```powershell
uv run python -m src.tools.generate_zhcn_assets `
    --companion-repo C:\path\to\Diablo4Companion `
    --d4data-repo C:\path\to\d4data `
    --d2core-dir C:\temp\d4lf-d2core `
    --en-us-dir .\assets\lang\enUS `
    --zhcn-grammar .\assets\lang\zhCN\grammar.json `
    --reviewed-overrides .\src\tools\data\reviewed_zhCN.json `
    --output-dir C:\temp\d4lf-zhcn\lang\zhCN `
    --catalog-dir C:\temp\d4lf-zhcn\catalog `
    --allow-unresolved
```

Without `--allow-unresolved`, the command returns `1` whenever the candidate is not release-ready. Invalid or
unreadable inputs return `2`. The generator never fills a missing Chinese value with English text.

`--reviewed-overrides` accepts normalized stable-ID translations that are safe to publish. The file must not
contain capture hashes, game builds, timestamps, UUIDs, record counts, or other evidence metadata. Unknown stable
IDs, empty translations, ASCII placeholders, and an `evidence` field fail generation. The public mapping file hash
is written to the locale manifest for reproducibility. It is calculated from canonical JSON content, so equivalent
LF and CRLF files have the same hash.

Translation precedence is reviewed override, paired Companion game data, then D2Core as a supplement when the
paired game data has no translation. No provider is authoritative by absence: a stable ID missing from the current
D2Core snapshot is never removed from the source manifest and never causes an existing non-empty Chinese alias to
be disabled at runtime. Each generated locale record includes a `translation_source` with its provider, source
identity, and translation hash; D2Core records also include a hash of the paired source record. Provider
disagreements are retained in `quality-report.json.translation_conflicts` and block release until explicitly
reviewed. The source manifest contains a derived D2Core translation-record index, and the release checker requires
each selected D2Core source ID, source-record hash, translation hash, and dataset namespace to match that index. A
D2Core/d4data build mismatch is allowed only for diagnostic candidate generation and forces `runtime_ready` to
remain false.

## Command

All input paths are explicit so the same checker works in a local checkout and CI:

```powershell
uv run python -m src.tools.locale_data_check `
    --source-lock path/to/source-lock.json `
    --build-version path/to/d4data/buildVersion.txt `
    --locale-manifest path/to/zhCN/manifest.json
```

Use `--source-manifest path/to/source-manifest.json` to override the source manifest path stored in the lock.
Use `--schema-version N` only while intentionally testing a new manifest schema. The supported default is schema
version 1.

## Update sequence

1. Update the d4data and Companion checkouts and record their exact commits and data builds.
1. Fetch a fresh bounded D2Core snapshot. Record its discovered build, eight source URLs, hashes, and documented
   attribution status; do not scrape or bypass the interactive planner.
1. Compare provider builds. A mixed-build candidate may be analyzed, but it cannot be promoted.
1. Regenerate the source manifest and source lock, including hashes for every declared source file.
1. Regenerate the target locale data and its manifest from that locked source. Do not hand-edit generated files
   after their hashes are recorded.
1. Confirm `excluded_historical_records` remains zero. The candidate checker rejects any nonzero value: provider
   snapshot absence is diagnostic metadata, not a reason to retire or hide a localized stable ID.
1. Run the checker with explicit paths. Preserve the JSON report as a CI artifact when the update is automated.
1. Review or commit the generated data only when the process exits with code 0 and the report has `"ok": true`.

## Schema version 1

Field names are snake case. SHA-256 values are 64 hexadecimal characters. Build versions are copied exactly from
d4data's `buildVersion.txt` without its trailing newline.

The source lock may embed `records`, or it may lock a separate source manifest:

```json
{
  "schema_version": 1,
  "build_version": "3.1.0.72592",
  "source_manifest": {
    "path": "source-manifest.json",
    "sha256": "<sha256 of the exact source-manifest.json bytes>"
  },
  "files": [
    {
      "path": "json/enUS_Text/meta/StringList/example.stl.json",
      "sha256": "<sha256 of the exact d4data file bytes>"
    }
  ]
}
```

Paths in the source lock's `files` array are relative to the directory containing `buildVersion.txt`. A separate
source manifest has this shape:

```json
{
  "schema_version": 1,
  "build_version": "3.1.0.72592",
  "records": [
    {
      "stable_id": "affixes:example",
      "text": "Example source text",
      "source_sha256": "<sha256 of the UTF-8 source text>"
    }
  ]
}
```

The generated locale manifest records the same stable IDs and the source hash used for each translation:

```json
{
  "schema_version": 1,
  "build_version": "3.1.0.72592",
  "locale": "zhCN",
  "source_manifest_sha256": "<sha256 of the exact source-manifest.json bytes>",
  "files": [
    {
      "path": "affixes.json",
      "sha256": "<sha256 of the exact generated file bytes>"
    }
  ],
  "records": [
    {
      "stable_id": "affixes:example",
      "text": "示例文本",
      "source_sha256": "<matching source record hash>",
      "translation_source": {
        "provider": "d2core",
        "source_id": "affix:Affix_Example:123:x1",
        "translation_sha256": "<hash of the selected Chinese text>",
        "source_record_sha256": "<hash of the paired enUS/zhCN source record>"
      }
    }
  ]
}
```

Generated file paths are relative to the locale manifest. Record hashes use the exact source text encoded as
UTF-8, with no whitespace or Unicode normalization. File and manifest hashes use the exact bytes on disk.

## Checks

The command rejects the update when any of these checks fail:

- Every manifest uses the expected schema version.
- The source lock, source manifest, generated locale manifest, and d4data `buildVersion.txt` agree.
- Locked manifests, declared source/generated files, source text hashes, and per-record source hashes match.
- Every locked D2Core dataset stays above its declared record floor, has equal enUS/zhCN counts, and every selected
  D2Core translation matches the locked derived record index.
- Source and locale stable-ID sets have complete one-to-one coverage.
- No stable ID is missing, newly introduced only in the locale, or duplicated in either manifest.
- Every locale record has translated text, and text containing ASCII letters is not ASCII-only. This catches
  copied source placeholders such as `Example source text`.

The checker deliberately has no ASCII exception switch. Translate an intentional acronym within its surrounding
text, or resolve the data policy in the manifest producer instead of silently weakening the gate.

## Output and exit codes

Standard output is one JSON object. `issues` contains stable codes such as `build_mismatch`, `hash_mismatch`,
`missing_record`, `new_record`, `duplicate_record`, and `ascii_placeholder`. `summary.issue_counts` is suitable for
CI annotations or update dashboards.

| Exit code | Meaning                                                                           |
| --------- | --------------------------------------------------------------------------------- |
| `0`       | All checks passed.                                                                |
| `1`       | Inputs were readable, but validation findings make the locale update unsafe.      |
| `2`       | Arguments or inputs were missing, unreadable, malformed, or structurally invalid. |

Treat every nonzero code as blocking. In particular, code 2 is not a skipped check; it means the checker could not
establish that the update is safe.

## Candidate and seasonal checks

The committed `zhCN` bundle supports guarded interaction while its quality report continues to declare unresolved
records. This command verifies that every release-gate `missing_record` is declared one-for-one in that report:

```powershell
uv run python -m src.tools.locale_candidate_check `
    --source-lock .\assets\catalog\source-lock.json `
    --build-version .\assets\catalog\d4data-buildVersion.txt `
    --locale-manifest .\assets\lang\zhCN\manifest.json `
    --quality-report .\assets\lang\zhCN\quality-report.json
```

Candidate consistency is not release approval. Promotion still requires `locale_data_check` itself to return
zero and the manifest to contain `"runtime_ready": true`.

The generator records intentionally excluded non-gear item types in `quality-report.json.scope`. They remain in
the runtime item-type JSON with empty aliases so historical English configuration keys stay stable, but they are
not source-manifest requirements and cannot block the zhCN equipment milestone.

The scheduled source watcher compares the locked d4data and D2Core builds plus all declared source hashes with
the current public upstream bytes:

```powershell
uv run python -m src.tools.season_data_watch `
    --source-manifest .\assets\catalog\source-manifest.json
```

It downloads only `buildVersion.txt`, the declared Companion files, D2Core's site bundle for build discovery, and
the eight locked D2Core static JSON files. Any build or file drift returns `1`; network, manifest, or encoding errors
return `2`.
