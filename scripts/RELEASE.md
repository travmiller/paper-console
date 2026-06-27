# PC-1 Release Workflow

This workflow creates deterministic production artifacts for non-git devices and publishes the GitHub releases the OTA updater consumes.

## What gets published

For each release version (example: `v1.2.3`), publish:

- `pc1-v1.2.3.tar.gz` (runtime bundle)
- `pc1-v1.2.3.sha256` (single checksum file)
- `release-manifest-v1.2.3.json` (metadata)
- Optional: `SHA256SUMS` (aggregate checksums for all release files)

## Release notes policy

Every GitHub release should include user-facing patch notes before the release is considered complete.

Patch notes appear in the PC-1 Settings UI, so write them for people using the device, not for developers reading git history:

- Describe visible behavior changes, fixes, setup impacts, and update caveats.
- Name the feature or module the user recognizes, such as Calendar, Updates, Slack, WiFi, or Print Endpoint.
- Avoid implementation details such as lockfiles, dependency churn, CI, refactors, test changes, internal filenames, or branch names unless they directly affect user behavior.
- Prefer concrete language: "Calendar events from large Google iCal feeds now print correctly" instead of "stream ICS response bodies."
- Keep notes non-empty. If a release only contains internal maintenance, summarize the user benefit or say there are no user-visible behavior changes.

Use `scripts/RELEASE_NOTES_TEMPLATE.md` as the starting point. After the tag-driven workflow publishes the GitHub release, add or verify notes with:

```bash
gh release edit v1.2.3 --notes-file scripts/RELEASE_NOTES_TEMPLATE.md
```

Replace the template content with release-specific notes before running that command.

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

## Recommended branch lanes

Use separate long-lived branches for the current stable line and the next release train:

- `main`: stable-ready branch. Only merge changes here that you would ship to the normal customer OTA lane.
- `beta`: next release train branch. This is where beta-only features can live for a while before they are ready for stable.

Mental model:

- `main` carries the current stable line, for example `v0.3.x`.
- `beta` carries prereleases for the next stable target, for example `v0.4.0-beta.1`, `v0.4.0-beta.2`, and so on.
- Beta is not just "slightly newer than stable." Beta is a preview of the next stable release train.

Example:

- stable line:
  - `v0.3.5`
  - `v0.3.6`
  - `v0.3.7`
- beta train for the next release:
  - `v0.4.0-beta.1`
  - `v0.4.0-beta.2`
  - `v0.4.0-rc.1`
  - later promoted to `v0.4.0`

For urgent production fixes:

1. Create a short-lived hotfix branch from the latest stable tag, for example `release/v1.2.3-hotfix`.
2. Apply only the production fix there.
3. Tag and publish the next stable release from that hotfix branch.
4. Cherry-pick the same fix onto `main` and `beta`.
5. Cut the next beta prerelease from the existing beta train so beta testers also receive the fix.

This keeps stable releases from accidentally inheriting beta-only modules or unfinished UI work, while still making it easy to land hotfixes on both lanes.

You can also run the workflow manually with `workflow_dispatch`, but normal day-to-day releases should use tag pushes so the Git tag and published release stay aligned.

## Stable release path

Use this path for the normal customer-facing OTA lane.

Stable tags should come from the current stable line on `main` or from a hotfix branch cut from the latest stable tag.

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

Use normal semver prerelease tags for the next stable train, for example:

- `v1.3.0-beta.1`
- `v1.3.0-beta.2`
- `v1.3.0-rc.1`

Use this path when you want the release to be available only to devices that explicitly opt into beta updates, while keeping the feature set ahead of stable.

Important versioning rule:

- Once stable is on `v1.2.x`, beta should normally move to the next release target such as `v1.3.0-beta.N`.
- Avoid using beta tags like `v1.2.4-beta.2` just to make beta appear "newer" than stable. That creates confusing version ordering and makes the release intent harder to reason about.

1. Build locally and sanity-check the bundle:

```bash
./.venv/bin/python scripts/release_build.py --version v1.3.0-beta.1 --build-web
```

2. Create and push the prerelease tag:

```bash
git tag v1.3.0-beta.1
git push origin v1.3.0-beta.1
```

3. Wait for the GitHub Actions release workflow to finish.

4. Verify GitHub published `v1.3.0-beta.1` as a **pre-release** and uploaded:
   - `pc1-v1.3.0-beta.1.tar.gz`
   - `pc1-v1.3.0-beta.1.sha256`
   - `release-manifest-v1.3.0-beta.1.json`
   - `SHA256SUMS`

OTA behavior:

- Devices on the default `stable` channel do not see prereleases.
- Devices with **General Settings → Updates → Beta Releases** enabled can see both prereleases and stable releases.
- The beta toggle only affects production OTA installs. Development installs still use git-based updates until converted to production.

Current implementation note:

- Devices on the `beta` channel receive the highest SemVer release across published prereleases and stable releases.
- Devices on the `stable` channel only receive published stable releases.
- Switching the **Beta Releases** toggle in General Settings changes which lane the device checks immediately.

Operational guidance:

- Because the updater currently compares beta and stable releases using SemVer ordering, keeping beta on the next train (`v1.3.0-beta.N` while stable is `v1.2.x`) avoids awkward edge cases.
- In other words: prefer train-based versioning rather than trying to keep beta "numerically ahead" with patch-level prereleases on the current stable line.

## Day-to-day release checklist

For a stable release:

1. Start from `main` only if it is already stable-ready. Otherwise create a hotfix branch from the latest stable tag and apply only the intended stable changes there.
2. Run local tests and build checks.
3. Run `npm audit` in `web/` and fix audit findings before tagging.
4. If dependency fixes rebuild `web/dist`, commit the lockfile and generated dist assets before tagging.
5. Push `vX.Y.Z`.
6. Confirm the GitHub release published successfully.
7. Add or verify user-facing GitHub release notes.
8. Confirm a production device on the stable channel sees the update and patch notes in General Settings.

For a beta release:

1. Merge the intended next-train changes to `beta`.
2. Run local tests and build checks.
3. Run `npm audit` in `web/` and fix audit findings before tagging.
4. If dependency fixes rebuild `web/dist`, commit the lockfile and generated dist assets before tagging.
5. Push a prerelease tag for the next stable target, such as `vX.(Y+1).0-beta.N` or `vX.(Y+1).0-rc.N`.
6. Confirm GitHub marked the release as a prerelease.
7. Add or verify user-facing GitHub release notes.
8. Confirm a production device with **Beta Releases** enabled sees the update and patch notes in General Settings.

For a stable hotfix that should also reach beta:

1. Create a hotfix branch from the latest stable tag.
2. Publish the next stable patch release from that hotfix branch.
3. Cherry-pick the same fix onto `main`.
4. Cherry-pick the same fix onto `beta`.
5. Publish the next beta prerelease from the existing beta train.

Example:

- stable today: `v0.3.6`
- beta train today: `v0.4.0-beta.2`
- urgent fix ships to stable as: `v0.3.7`
- same fix then ships to beta as: `v0.4.0-beta.3`

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
