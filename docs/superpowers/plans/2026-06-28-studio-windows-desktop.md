# Studio Windows Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Windows x64 preview release path for ANIP Studio Desktop.

**Architecture:** Reuse the existing Tauri desktop shell and Python Studio API sidecar. Make the sidecar build script platform-aware, then add a Windows GitHub Actions workflow that produces unsigned installer artifacts for manual validation.

**Tech Stack:** Tauri 2, Rust stable, Node 22, Python 3.12, PyInstaller, GitHub Actions `windows-latest`.

---

### Task 1: Make The Sidecar Build Script Portable

**Files:**
- Modify: `studio/scripts/build-desktop-api-sidecar.sh`

- [ ] **Step 1: Add platform-aware PyInstaller path and add-data separator**

Change the script so Windows uses `.venv/Scripts/pyinstaller.exe` and `;` for PyInstaller `--add-data`, while Unix-like platforms keep `.venv/bin/pyinstaller` and `:`.

- [ ] **Step 2: Replace hard-coded `--add-data` separators**

Introduce a small helper variable such as `ADD_DATA_SEPARATOR` and use `"${source}${ADD_DATA_SEPARATOR}${dest}"` for every `--add-data` value.

- [ ] **Step 3: Validate shell syntax**

Run:

```bash
bash -n studio/scripts/build-desktop-api-sidecar.sh
```

Expected: no output and exit code `0`.

### Task 2: Add Windows Desktop Publish Workflow

**Files:**
- Create: `.github/workflows/publish-studio-desktop-windows.yml`

- [ ] **Step 1: Add manual dispatch inputs**

Inputs:

- `version`, required, example `0.9.0`.
- `source_ref`, required, default `main`.
- `release_tag`, optional, default empty.

- [ ] **Step 2: Add Windows x64 build job**

Use `windows-latest`. Set `VERSION` from workflow input.

- [ ] **Step 3: Install dependencies**

Install Python 3.12, create `.venv`, install `studio/server/desktop-build-requirements.txt`, set up Node 22, run `npm --prefix studio ci`, run `npm --prefix packages/typescript/vue install --include=dev --no-package-lock`, set Rust stable.

- [ ] **Step 4: Patch release metadata at build time**

Mirror the macOS workflow metadata patch for `studio/package.json`, `studio/package-lock.json`, `studio/src/version.ts`, `studio/src-tauri/tauri.conf.json`, `studio/src-tauri/Cargo.toml`, and `studio/src-tauri/Cargo.lock`.

- [ ] **Step 5: Build sidecar and Tauri app**

Run:

```powershell
npm --prefix studio run build:desktop-api
npm --prefix studio exec -- tauri build
```

- [ ] **Step 6: Locate and upload artifacts**

Find artifacts under:

- `studio/src-tauri/target/release/bundle/nsis`
- `studio/src-tauri/target/release/bundle/msi`

Upload all files found under those directories.

- [ ] **Step 7: Optionally attach to release**

If `release_tag` is provided, create the GitHub Release if missing and upload all Windows artifacts with `--clobber`.

### Task 3: Verify

**Files:**
- Modified/created files from Tasks 1 and 2.

- [ ] **Step 1: Parse workflow YAML**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
for path in [
    Path('.github/workflows/publish-studio-desktop-windows.yml'),
]:
    yaml.safe_load(path.read_text())
print('YAML parsed')
PY
```

Expected: `YAML parsed`.

- [ ] **Step 2: Check git diff**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-28-studio-windows-desktop-design.md \
  docs/superpowers/plans/2026-06-28-studio-windows-desktop.md \
  studio/scripts/build-desktop-api-sidecar.sh \
  .github/workflows/publish-studio-desktop-windows.yml
git commit -m "Add Windows Studio desktop preview workflow"
```

- [ ] **Step 4: Open PR**

```bash
git push -u origin studio-windows-desktop-preview
gh pr create --base main --head studio-windows-desktop-preview --title "Add Windows Studio desktop preview workflow"
```

Expected: PR URL is returned.

