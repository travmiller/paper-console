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
- On Raspberry Pi devices, install `requirements-pi.txt` during provisioning

## Build artifacts locally

```bash
./.venv/bin/python scripts/release_build.py --version v1.2.3 --build-web
```

On Windows, run this command from WSL.

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

## Beta releases

Use normal semver prerelease tags for beta/RC builds, for example:

- `v1.2.3-beta.1`
- `v1.2.3-beta.2`
- `v1.2.3-rc.1`

Build and publish them the same way as stable releases:

```bash
./.venv/bin/python scripts/release_build.py --version v1.2.3-beta.1 --build-web
git tag v1.2.3-beta.1
git push origin v1.2.3-beta.1
```

Then create the GitHub release for that tag and mark it as a **pre-release**.

OTA behavior:

- Devices on the default `stable` channel only check GitHub's latest stable release.
- Devices with **General Settings → Updates → Beta Releases** enabled opt into prerelease OTA behavior.

Current implementation note:

- The beta channel currently follows the newest published non-draft release returned by GitHub's full releases list, not a separately labeled "latest beta" concept.
- If you publish a newer stable release after a beta release, beta-enabled devices may follow that newer stable release.
- If you need a strictly isolated beta lane, use a separate beta release repo until update-channel behavior becomes more specific.

## Factory image guidance

- Ship units from artifacts (no `.git` folder).
- Include `.version` file containing the shipped release tag.
- Keep `config.json` user-owned and not baked with secrets.
- Before capturing the golden SD image, run:
  - `sudo ./scripts/prepare_golden_image.sh --yes`
  - Optional size optimization: `sudo ./scripts/prepare_golden_image.sh --yes --zero-free-space`

## OTA expectations

Production OTA requires the explicit release asset `pc1-<tag>.tar.gz`.

This runtime bundle must already include built frontend assets under `web/dist`.
Production devices do not build the UI on-device and should not depend on Node/npm being installed.
