# Studio Desktop macOS Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated GitHub Actions release workflow that builds, signs, notarizes, verifies, and uploads the ANIP Studio macOS DMG.

**Architecture:** Keep Studio desktop publishing independent from protocol package releases and Docker image publishing. The workflow imports Apple signing credentials from GitHub Actions secrets into a temporary keychain, builds the existing Tauri app, verifies notarization, and uploads the DMG artifact.

**Tech Stack:** GitHub Actions, macOS runner, Tauri v2, npm, Rust/Cargo, PyInstaller sidecar build, Apple Developer ID signing, Apple notarytool/stapler.

---

### Task 1: Add Dedicated macOS Desktop Publishing Workflow

**Files:**
- Create: `.github/workflows/publish-studio-desktop-macos.yml`

- [ ] **Step 1: Create workflow with manual inputs**

Create `.github/workflows/publish-studio-desktop-macos.yml` with `workflow_dispatch` inputs:

```yaml
name: Publish Studio macOS Desktop

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Studio desktop app version tag (e.g., 0.9.0)"
        required: true
      source_ref:
        description: "Git ref to build from"
        required: true
        default: "main"
      release_tag:
        description: "Optional GitHub Release tag to attach the DMG to"
        required: false
        default: ""
```

- [ ] **Step 2: Add macOS job and required secrets preflight**

The job must run on `macos-latest`, require read-only repository contents by default, and fail early if any required Apple signing secret is missing.

- [ ] **Step 3: Import Developer ID certificate into a temporary keychain**

Decode `APPLE_CERTIFICATE`, import it with `APPLE_CERTIFICATE_PASSWORD`, unlock the temporary keychain with `KEYCHAIN_PASSWORD`, and configure the key partition list for `codesign`.

- [ ] **Step 4: Write App Store Connect API key to a temporary file**

Write `APPLE_API_KEY_P8` to `$RUNNER_TEMP/AuthKey_${APPLE_API_KEY}.p8` with mode `600`. Export `APPLE_API_KEY_PATH`, `APPLE_API_ISSUER`, `APPLE_API_KEY`, `APPLE_TEAM_ID`, and `APPLE_SIGNING_IDENTITY` for the Tauri build.

- [ ] **Step 5: Patch Studio/Tauri app version for the release build**

Use Node to update:

```text
studio/package.json
studio/package-lock.json
studio/src/version.ts
studio/src-tauri/tauri.conf.json
studio/src-tauri/Cargo.toml
studio/src-tauri/Cargo.lock
```

The workflow should not commit these changes; they are build-time metadata only.

- [ ] **Step 6: Install dependencies and build the app**

Run:

```bash
npm --prefix studio ci
npm --prefix studio run desktop:build
```

- [ ] **Step 7: Verify signing and notarization**

Verify the generated app and DMG:

```bash
codesign --verify --deep --strict --verbose=2 "studio/src-tauri/target/release/bundle/macos/ANIP Studio.app"
spctl -a -vvv -t install "studio/src-tauri/target/release/bundle/dmg/ANIP Studio_${VERSION}_aarch64.dmg"
xcrun stapler validate "studio/src-tauri/target/release/bundle/dmg/ANIP Studio_${VERSION}_aarch64.dmg"
```

- [ ] **Step 8: Upload the DMG artifact**

Upload the generated DMG as `anip-studio-macos-${VERSION}` using `actions/upload-artifact`.

- [ ] **Step 9: Optionally attach the DMG to a GitHub Release**

If `release_tag` is non-empty, use GitHub CLI to upload the DMG to that release with `--clobber`.

- [ ] **Step 10: Validate workflow syntax locally**

Run a lightweight parser check:

```bash
ruby -e "require 'yaml'; YAML.load_file('.github/workflows/publish-studio-desktop-macos.yml'); puts 'ok'"
```

Expected output:

```text
ok
```

- [ ] **Step 11: Commit and open PR**

```bash
git add .github/workflows/publish-studio-desktop-macos.yml docs/superpowers/plans/2026-06-28-studio-desktop-macos-release.md
git commit -m "Add Studio macOS desktop release workflow"
git push -u origin studio-desktop-macos-release
gh pr create --base main --head studio-desktop-macos-release --title "Add Studio macOS desktop release workflow" --body "<summary and verification>"
```

---

## Self-Review

- Spec coverage: The workflow is separate from Docker/protocol releases, uses Apple Developer ID signing, notarization credentials, verification, and artifact upload.
- Placeholder scan: No placeholders or deferred steps are present; optional release upload is explicitly controlled by `release_tag`.
- Type consistency: Workflow input and environment names match the GitHub secrets already requested from the user.
