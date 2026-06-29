# ANIP Studio Windows Desktop Design

Issue: [#272 Ship ANIP Studio as a Windows desktop application](https://github.com/anip-protocol/anip/issues/272)

## Goal

Ship a first Windows x64 preview build of ANIP Studio Desktop using the same Tauri shell, bundled Studio API sidecar, SQLite desktop storage, and showcase snapshot preload model as the macOS desktop app.

## First Slice

The first slice is intentionally narrow:

- Build Windows x64 only.
- Produce unsigned preview installer artifacts from GitHub Actions.
- Upload artifacts to the workflow run.
- Defer Windows ARM64, code signing, auto-update, and Microsoft Store publication until the x64 build installs and runs on a real Windows machine.

This avoids creating a signing/store workflow before we know the application packaging, sidecar startup, SQLite storage, local loopback API, and showcase preload behavior work on Windows.

## Architecture

The existing Tauri desktop shell remains the application boundary. It starts the bundled Studio API sidecar, passes desktop-mode environment variables, and points the web UI at the dynamically selected localhost API port.

The existing Python sidecar build path is reused, but the build script must be platform-aware:

- Windows sidecar name: `anip-studio-api-x86_64-pc-windows-msvc.exe`.
- Windows PyInstaller executable path: `.venv/Scripts/pyinstaller.exe`.
- Windows PyInstaller `--add-data` separator: `;`.
- Unix/macOS PyInstaller `--add-data` separator: `:`.

The Windows GitHub Actions workflow builds the sidecar, runs Tauri packaging, locates installer artifacts, and uploads them. It does not sign the installer in this first slice.

## User Experience

The preview artifact is for manual validation on a Windows x64 laptop. Expected behavior:

- Install or unpack the generated artifact.
- Launch ANIP Studio.
- Design mode starts without requiring Docker, Python, Node, Rust, or a repo checkout.
- The bundled API sidecar starts automatically.
- Studio uses local SQLite storage.
- Showcase projects preload.

Unsigned Windows builds may show SmartScreen or trust warnings. That is acceptable for this preview slice and must be documented before broader publication.

## Non-Goals

- Windows ARM64 build.
- Microsoft Store submission.
- Production Windows code-signing certificate setup.
- Auto-update.
- Reworking desktop storage or sidecar architecture.

## Acceptance Criteria

- Windows x64 workflow exists and can be manually dispatched.
- Workflow installs Python, Node, Rust, Studio dependencies, and desktop API build dependencies.
- Workflow builds the Windows API sidecar with the correct `.exe` name.
- Workflow builds Tauri Windows bundle artifacts.
- Workflow uploads installer artifacts.
- The implementation does not affect the macOS desktop workflow.

