# Release QA & Promote Checklist

Erudi ships via a **release-candidate gate**: a tag builds a signed/notarized
**draft** release; a maintainer QA-tests the **exact** draft artifact, then
**promotes** it so clients receive it through auto-update.

```
git tag vX.Y.Z && git push --tags
        │
        ▼
CI (release.yml): build backend + app, sign + notarize (mac) → publish DRAFT
        │
        ▼
QA tester downloads the DRAFT artifact for their platform, runs the scenarios
below on the EXACT signed bits (same appId, same data dir — no modifications)
        │
        ├── KO → delete the draft + tag, fix, re-tag
        ▼
OK → promote: un-draft + write changelog → latest*.yml goes live → clients auto-update
```

A draft is **never** offered by electron-updater (its feed 404s while drafted), so
clients are untouched until the maintainer promotes it.

## Why we test the draft as-is (no isolation tooling)

We deliberately do **not** use a separate appId / data dir / env override for QA:
the goal is **zero deviation** from what ships. Instead, by convention:

- **QA testers do not keep a "production" Erudi with precious data** on their test
  machine — they are developers, not clients. Their Erudi data is disposable.
- This also gives the **upgrade path test for free**: keeping the data dir from a
  previous version and installing the new RC exercises the real client migration
  path (see #96).

Safety net: once DB migrations land (#96), the pre-upgrade **data-dir backup**
protects testers from a bad destructive migration — the same mechanism that
protects clients.

### Reset to a clean slate (fresh-install scenario)

Quit Erudi, delete the data dir, relaunch:

- **macOS**: `~/Library/Application Support/erudi/`
- **Windows**: `%APPDATA%\erudi\` (the `runtime_paths` packaged data root)

(Keep the dir to test an **upgrade** instead of a fresh install.)

## QA scenarios (per platform)

Run on the downloaded draft, **not** a local build:

- [ ] App launches; backend reaches ready; main window loads.
- [ ] Chat: download a small model, send a prompt, response streams.
- [ ] KB: ingest a document (embeddings complete), attach it, ask a grounded
      question → answer cites the source.
- [ ] (If applicable) multimodal: chat with an image.
- [ ] Auto-update visibility: the draft is **not** offered to an installed stable
      build (sanity — it should not be).
- [ ] **Upgrade** (when relevant): install the previous version, use it briefly,
      then install this RC over it → data intact, schema migrated, no crash.

## Platform coverage (assign one tester per artifact)

| Artifact | Owner(s) |
|---|---|
| macOS Apple Silicon | Rayan |
| Windows CUDA | (NVIDIA machine) |
| Windows CPU | Rayan / Yolaatar |
| Linux CUDA / CPU / ROCm | future (machines TBD) |
| macOS Intel | future (deprecation pending) |

Record who tested which artifact in the release notes.

## Promote

When all assigned artifacts pass:

1. Edit the draft GitHub Release: add the changelog.
2. Un-draft (publish) — keep "latest" for stable, or flag prerelease for betas.
3. Verify an installed older build detects + applies the update end-to-end.
