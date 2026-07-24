# Third-party data

This file records publication requirements for generated or bundled data whose provenance is separate from D4LF's
MIT software license.

## D2Core

**Public redistribution status: documented.**

The zhCN catalog and generated locale bundle contain normalized records derived from D2Core's public static data
endpoints. The project owner has confirmed that these data may be directly used, normalized, bundled, and publicly
redistributed by this project. Public releases must acknowledge D2Core in the README and preserve source URLs,
source build identifiers, and hashes in the generated manifests. This attribution does not imply D2Core endorsement
of D4LF or its releases.

Affected generated paths include:

- `assets/catalog/source-manifest.json`
- `assets/catalog/source-lock.json`
- `assets/lang/zhCN/*.json`

The machine-readable status is `documented`; regeneration must not silently change it back to `unverified`.

## Diablo4Companion

The primary stable-ID `enUS`/`zhCN` pairs are derived from
[Diablo4Companion](https://github.com/josdemmers/Diablo4Companion), which is distributed under the MIT License.
Public source trees and binary release archives must include `THIRD-PARTY-NOTICES.md`, including the upstream
copyright and permission notice.

## DiabloTools d4data

Game build identifiers and stable internal metadata are cross-checked against
[DiabloTools/d4data](https://github.com/DiabloTools/d4data), which is distributed under the MIT License. Public
source trees and binary release archives must include its upstream copyright and permission notice in
`THIRD-PARTY-NOTICES.md`. Direct Diablo IV game text and assets remain the property of Blizzard Entertainment.
