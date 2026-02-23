# PC-1 Release Workflow

This workflow creates deterministic production artifacts for non-git devices and publishes files the OTA updater can consume.

## What gets published

For each release version (example: `v1.2.3`), publish:

- `pc1-v1.2.3.tar.gz` (runtime bundle)
- `pc1-v1.2.3.sha256` (single checksum file)
- `release-manifest-v1.2.3.json` (metadata)
- Optional: `SHA256SUMS` (aggregate checksums for all release files)

## One-time prerequisites

- Ensure `web/` builds successfully (`npm ci && npm run build`)
- Ensure backend tests pass
- Decide semantic version tag (`vX.Y.Z`)

## Build artifacts locally

```bash
./.venv/bin/python scripts/release_build.py --version v1.2.3 --build-web
```

Windows:

```powershell
.\.venv\Scripts\python.exe scripts\release_build.py --version v1.2.3 --build-web
```

Artifacts are written to `release-artifacts/` by default.

## Publish to GitHub release

1. Create and push tag:

```bash
git tag v1.2.3
git push origin v1.2.3
```

2. Create a GitHub release for `v1.2.3`.
3. Upload these files as release assets:
   - `pc1-v1.2.3.tar.gz`
   - `pc1-v1.2.3.sha256`
   - `release-manifest-v1.2.3.json`

Optional hardening:
- Upload `SHA256SUMS` and include `pc1-v1.2.3.tar.gz` checksum line.
- Set `PC1_UPDATE_TARBALL_SHA256` on devices as a pinned expected hash.

## Factory image guidance

- Ship units from artifacts (no `.git` folder).
- Include `.version` file containing the shipped release tag.
- Keep `config.json` user-owned and not baked with secrets.

## OTA expectations

Production OTA now prefers release asset `pc1-<tag>.tar.gz`. If not found, it falls back to GitHub's source tarball.

Recommended: always attach the explicit `pc1-<tag>.tar.gz` asset so updates do not depend on Node/npm availability on-device.
