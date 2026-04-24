# PC-1 Release Workflow

This workflow creates deterministic production artifacts for non-git devices and publishes the GitHub releases the OTA updater consumes.

## What gets published

For each release version (example: `v1.2.3`), publish:

- `pc1-v1.2.3.tar.gz` (runtime bundle)
- `pc1-v1.2.3.sha256` (single checksum file)
- `release-manifest-v1.2.3.json` (metadata)
- Optional: `SHA256SUMS` (aggregate checksums for all release files)

## One-time prerequisites

- Ensure `web/` builds successfully (`npm ci && npm run build`)
- Ensure backend tests pass
- Decide whether this is a stable tag (`vX.Y.Z`) or prerelease tag (`vX.Y.Z-beta.N`, `vX.Y.Z-rc.N`)
- On Raspberry Pi devices, install `requirements-pi.txt` during provisioning

## Build artifacts locally

```bash
./.venv/bin/python scripts/release_build.py --version v1.2.3 --build-web
```

On Windows, run this command from WSL.

Artifacts are written to `release-artifacts/` by default.

Local artifact note:

- Locally generated artifacts are for sanity-checking only. After the tag-driven GitHub release publishes successfully, the GitHub release assets are the canonical OTA artifacts.
- Remove any untracked local artifacts for that version after publishing, unless you explicitly need to keep a copy for device-side manual testing.
- Do not commit ad hoc local release artifacts as part of normal stable or beta release prep.

## Release automation

The canonical publish path is a Git tag push.

- Pushing any tag that matches `v*` triggers `.github/workflows/release-artifacts.yml`.
- The workflow runs tests, clears `release-artifacts/`, builds the OTA bundle, generates `SHA256SUMS`, and publishes a GitHub release automatically.
- Tags with a hyphen, such as `v1.2.3-beta.1`, are published as GitHub prereleases.
- Tags without a hyphen, such as `v1.2.3`, are published as normal stable releases.

You can also run the workflow manually with `workflow_dispatch`, but normal day-to-day releases should use tag pushes so the Git tag and published release stay aligned.

## Stable release path

Use this path for the normal customer-facing OTA lane.

1. Build locally and sanity-check the bundle:

```bash
./.venv/bin/python scripts/release_build.py --version v1.2.3 --build-web
```

2. Create and push the stable tag:

```bash
git tag v1.2.3
git push origin v1.2.3
```

3. Wait for the GitHub Actions release workflow to finish.

4. Verify the release page for `v1.2.3` contains:
   - `pc1-v1.2.3.tar.gz`
   - `pc1-v1.2.3.sha256`
   - `release-manifest-v1.2.3.json`
   - `SHA256SUMS`

Stable OTA behavior:

- Production devices on the default `stable` channel choose the highest SemVer stable release from GitHub releases.
- A newly published stable release becomes the update target for stable devices automatically.

Optional hardening:
- Set `PC1_UPDATE_TARBALL_SHA256` on devices as a pinned expected hash.

## Beta release path

Use normal semver prerelease tags for beta/RC builds, for example:

- `v1.2.3-beta.1`
- `v1.2.3-beta.2`
- `v1.2.3-rc.1`

Use this path when you want the release to be available only to devices that explicitly opt into beta updates.

1. Build locally and sanity-check the bundle:

```bash
./.venv/bin/python scripts/release_build.py --version v1.2.3-beta.1 --build-web
```

2. Create and push the prerelease tag:

```bash
git tag v1.2.3-beta.1
git push origin v1.2.3-beta.1
```

3. Wait for the GitHub Actions release workflow to finish.

4. Verify GitHub published `v1.2.3-beta.1` as a **pre-release** and uploaded:
   - `pc1-v1.2.3-beta.1.tar.gz`
   - `pc1-v1.2.3-beta.1.sha256`
   - `release-manifest-v1.2.3-beta.1.json`
   - `SHA256SUMS`

OTA behavior:

- Devices on the default `stable` channel do not see prereleases.
- Devices with **General Settings → Updates → Beta Releases** enabled can see both prereleases and stable releases.
- The beta toggle only affects production OTA installs. Development installs still use git-based updates until converted to production.

Current implementation note:

- Devices on the `beta` channel receive the highest SemVer release across published prereleases and stable releases.
- Devices on the `stable` channel only receive published stable releases.
- Switching the **Beta Releases** toggle in General Settings changes which lane the device checks immediately.

## Day-to-day release checklist

For a stable release:

1. Merge the intended changes to `main`.
2. Run local tests and build checks.
3. Run `npm audit` in `web/` and fix audit findings before tagging.
4. If dependency fixes rebuild `web/dist`, commit the lockfile and generated dist assets before tagging.
5. Push `vX.Y.Z`.
6. Confirm the GitHub release published successfully.
7. Confirm a production device on the stable channel sees the update in General Settings.

For a beta release:

1. Merge the intended changes to `main`.
2. Run local tests and build checks.
3. Run `npm audit` in `web/` and fix audit findings before tagging.
4. If dependency fixes rebuild `web/dist`, commit the lockfile and generated dist assets before tagging.
5. Push `vX.Y.Z-beta.N` or `vX.Y.Z-rc.N`.
6. Confirm GitHub marked the release as a prerelease.
7. Confirm a production device with **Beta Releases** enabled sees the update in General Settings.

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
