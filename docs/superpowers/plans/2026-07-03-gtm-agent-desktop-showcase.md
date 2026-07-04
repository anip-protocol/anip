# GTM Agent Desktop Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Mac/Windows installable GTM Agent showcase app that runs without Docker, terminal commands, or external BI setup.

**Architecture:** Package a Tauri desktop shell around the existing GTM Agent UI and a local Python sidecar. The sidecar runs the agent runtime plus four generated ANIP service endpoints against a bundled local GTM data store. The desktop app is the non-technical product demo path; Docker Compose remains the full architecture and five-language verification path.

**Tech Stack:** Tauri 2, Rust sidecar process management, FastAPI/Uvicorn, PyInstaller, bundled SQLite/DuckDB-ready data artifacts, existing Python GTM generated service implementation, existing GTM Agent HTML UI.

---

## File Structure

- Create `examples/showcase/gtm/desktop/README.md`: explains desktop goals, scope, and differences from Docker Compose.
- Create `examples/showcase/gtm/desktop/package.json`: local build scripts for the GTM desktop shell.
- Create `examples/showcase/gtm/desktop/index.html`: startup host for the GTM desktop shell.
- Create `examples/showcase/gtm/desktop/src/main.ts`: minimal web entry that points to the embedded local sidecar.
- Create `examples/showcase/gtm/desktop/src-tauri/tauri.conf.json`: Tauri app config for GTM Agent Desktop.
- Create `examples/showcase/gtm/desktop/src-tauri/src/main.rs`: Tauri entrypoint.
- Create `examples/showcase/gtm/desktop/src-tauri/src/lib.rs`: sidecar launch, dynamic local port assignment, browser window handoff.
- Create `examples/showcase/gtm/desktop/sidecar/gtm_desktop_api.py`: Python sidecar entrypoint wrapping the GTM Agent runtime.
- Create `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`: static tests for config, sidecar env, and no-Docker contract.
- Create `.github/workflows/publish-gtm-desktop.yml`: later release workflow for signed desktop artifacts.
- Modify `website/docs/showcases/gtm-agent/overview.md`: add Desktop Showcase path after it exists.
- Modify `website/docs/showcases/gtm-agent/docker-compose.md`: explicitly position Docker as technical/full-stack verification, not first-run path.

## Constraints

- The desktop app must not require Docker Desktop.
- The desktop app must not require users to run terminal commands.
- The desktop app may require an OpenAI-compatible API key for live agent questions.
- The first implementation should use Python as the canonical embedded service runtime because it already has the mature GTM agent/runtime path.
- The desktop app should not claim five-language local execution. Five-language parity remains validated by generated services and CI.
- The app must make missing API key setup visible and actionable inside the UI.
- The app must not bundle Metabase for the first milestone. It should provide built-in evidence/BI preview pages and link to Docker Compose for full Metabase verification.

---

### Task 1: Add Desktop Showcase Plan and Static Contract Tests

**Files:**
- Create: `examples/showcase/gtm/desktop/README.md`
- Create: `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`

- [ ] **Step 1: Write the desktop README**

Create `examples/showcase/gtm/desktop/README.md`:

```markdown
# GTM Agent Desktop Showcase

The GTM Agent Desktop Showcase is the non-Docker path for trying the GTM Agent.

It is intended for PM, business, and evaluation users who want to install an
app, enter an OpenAI-compatible API key, and try governed GTM questions without
learning Docker Compose.

## Scope

- Runs the GTM Agent UI locally.
- Starts embedded local ANIP service sidecars automatically.
- Uses bundled sample GTM data.
- Supports questions, approvals, evidence, and runbook views.
- Uses one canonical generated implementation for the embedded demo.

## Not In Scope

- Running all five language implementations inside the desktop app.
- Bundling Metabase.
- Replacing the Docker Compose full-stack architecture proof.

## Relationship to Docker Compose

The desktop app is the product demo path. Docker Compose remains the technical
verification path for Postgres, dbt, Metabase, and five generated language
stacks.
```

- [ ] **Step 2: Write static contract tests**

Create `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_positions_desktop_as_non_docker_path():
    readme = (ROOT / "README.md").read_text()

    assert "non-Docker path" in readme
    assert "Docker Compose remains the technical" in readme
    assert "Bundling Metabase" in readme


def test_desktop_contract_for_first_milestone():
    readme = (ROOT / "README.md").read_text()

    assert "one canonical generated implementation" in readme
    assert "OpenAI-compatible API key" in readme
    assert "embedded local ANIP service sidecars" in readme
```

- [ ] **Step 3: Run tests**

Run:

```bash
pytest examples/showcase/gtm/desktop/tests/test_desktop_contract.py
```

Expected: `2 passed`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-03-gtm-agent-desktop-showcase.md examples/showcase/gtm/desktop/README.md examples/showcase/gtm/desktop/tests/test_desktop_contract.py
git commit -m "Plan GTM Agent desktop showcase"
```

---

### Task 2: Create Minimal Tauri Shell

**Files:**
- Create: `examples/showcase/gtm/desktop/package.json`
- Create: `examples/showcase/gtm/desktop/index.html`
- Create: `examples/showcase/gtm/desktop/src/main.ts`
- Create: `examples/showcase/gtm/desktop/src-tauri/Cargo.toml`
- Create: `examples/showcase/gtm/desktop/src-tauri/src/main.rs`
- Create: `examples/showcase/gtm/desktop/src-tauri/src/lib.rs`
- Create: `examples/showcase/gtm/desktop/src-tauri/tauri.conf.json`
- Modify: `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`

- [ ] **Step 1: Extend test for shell files**

Append to `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`:

```python
def test_tauri_shell_files_exist():
    expected = [
        "package.json",
        "index.html",
        "src/main.ts",
        "src-tauri/Cargo.toml",
        "src-tauri/src/main.rs",
        "src-tauri/src/lib.rs",
        "src-tauri/tauri.conf.json",
    ]

    for relative_path in expected:
        assert (ROOT / relative_path).exists(), relative_path
```

- [ ] **Step 2: Add package scripts**

Create `examples/showcase/gtm/desktop/package.json`:

```json
{
  "name": "@anip-dev/gtm-agent-desktop-showcase",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc --noEmit && vite build",
    "tauri": "tauri"
  },
  "dependencies": {
    "@tauri-apps/api": "^2.9.0"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.9.0",
    "typescript": "^5.9.0",
    "vite": "^8.0.0"
  }
}
```

- [ ] **Step 3: Add web entry**

Create `examples/showcase/gtm/desktop/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GTM Agent Desktop</title>
  </head>
  <body>
    <main id="app">
      <h1>Starting GTM Agent</h1>
      <p>Preparing the local ANIP services and bundled GTM demo workspace.</p>
    </main>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 4: Add initial TypeScript entry**

Create `examples/showcase/gtm/desktop/src/main.ts`:

```ts
const app = document.querySelector<HTMLDivElement>('#app')

if (app) {
  app.innerHTML = `
    <section style="font-family: Avenir Next, Segoe UI, sans-serif; padding: 48px; color: #f4efe5; background: #101820; min-height: 100vh;">
      <p style="color: #f29d38; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; font-weight: 800;">ANIP Showcase</p>
      <h1 style="font-size: 42px; margin: 8px 0;">GTM Agent Desktop</h1>
      <p style="max-width: 720px; line-height: 1.6; color: #c8d1da;">
        This desktop shell will start the embedded GTM Agent runtime and local ANIP services without Docker.
      </p>
    </section>
  `
}
```

- [ ] **Step 5: Add Rust/Tauri skeleton**

Create `examples/showcase/gtm/desktop/src-tauri/Cargo.toml`:

```toml
[package]
name = "gtm-agent-desktop"
version = "0.1.0"
edition = "2021"

[lib]
name = "gtm_agent_desktop_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-opener = "2"
```

Create `examples/showcase/gtm/desktop/src-tauri/src/main.rs`:

```rust
fn main() {
    gtm_agent_desktop_lib::run();
}
```

Create `examples/showcase/gtm/desktop/src-tauri/src/lib.rs`:

```rust
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("error while running GTM Agent Desktop");
}
```

- [ ] **Step 6: Add Tauri config**

Create `examples/showcase/gtm/desktop/src-tauri/tauri.conf.json`:

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "GTM Agent Desktop",
  "version": "0.1.0",
  "identifier": "dev.anip.gtm-agent",
  "build": {
    "beforeDevCommand": "npm run dev",
    "devUrl": "http://127.0.0.1:5173",
    "beforeBuildCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "GTM Agent Desktop",
        "width": 1280,
        "height": 900,
        "minWidth": 1024,
        "minHeight": 720,
        "resizable": true,
        "fullscreen": false,
        "backgroundColor": "#101820"
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "category": "Business",
    "shortDescription": "Installable GTM Agent showcase for ANIP",
    "longDescription": "A local GTM Agent demo that runs governed ANIP services without Docker."
  }
}
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest examples/showcase/gtm/desktop/tests/test_desktop_contract.py
```

Expected: `3 passed`.

- [ ] **Step 8: Commit**

```bash
git add examples/showcase/gtm/desktop
git commit -m "Add GTM Agent desktop shell"
```

---

### Task 3: Add Sidecar Contract and API Skeleton

**Files:**
- Create: `examples/showcase/gtm/desktop/sidecar/gtm_desktop_api.py`
- Create: `examples/showcase/gtm/desktop/sidecar/requirements.txt`
- Modify: `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`

- [ ] **Step 1: Add sidecar tests**

Append to `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`:

```python
def test_sidecar_exposes_desktop_health_and_runtime_contract():
    sidecar = (ROOT / "sidecar" / "gtm_desktop_api.py").read_text()

    assert "@app.get(\"/desktop/health\")" in sidecar
    assert "@app.get(\"/desktop/config\")" in sidecar
    assert "requires_api_key" in sidecar
    assert "docker_required" in sidecar
```

- [ ] **Step 2: Add sidecar API**

Create `examples/showcase/gtm/desktop/sidecar/gtm_desktop_api.py`:

```python
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="GTM Agent Desktop API")


@app.get("/desktop/health")
def health() -> dict[str, str]:
    return {"status": "ok", "runtime": "gtm-agent-desktop"}


@app.get("/desktop/config")
def config() -> JSONResponse:
    has_key = bool(
        (os.getenv("ANIP_AGENT_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    )
    return JSONResponse(
        {
            "runtime": "gtm-agent-desktop",
            "requires_api_key": not has_key,
            "docker_required": False,
            "embedded_services": ["pipeline", "enrichment", "prioritization", "outreach"],
            "data_profile": "bundled_gtm_sample",
        }
    )
```

- [ ] **Step 3: Add sidecar requirements**

Create `examples/showcase/gtm/desktop/sidecar/requirements.txt`:

```text
fastapi>=0.115.0
uvicorn>=0.30.0
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest examples/showcase/gtm/desktop/tests/test_desktop_contract.py
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add examples/showcase/gtm/desktop
git commit -m "Add GTM Agent desktop sidecar skeleton"
```

---

### Task 4: Add Data Portability Adapter Design

**Files:**
- Create: `examples/showcase/gtm/desktop/DATA_PORTABILITY.md`
- Modify: `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`

- [ ] **Step 1: Add portability test**

Append to `examples/showcase/gtm/desktop/tests/test_desktop_contract.py`:

```python
def test_data_portability_document_defines_sqlite_or_duckdb_path():
    doc = (ROOT / "DATA_PORTABILITY.md").read_text()

    assert "Postgres remains the Docker verification path" in doc
    assert "SQLite" in doc or "DuckDB" in doc
    assert "dbt marts must be prebuilt" in doc
```

- [ ] **Step 2: Add portability document**

Create `examples/showcase/gtm/desktop/DATA_PORTABILITY.md`:

```markdown
# GTM Desktop Data Portability

The Docker showcase uses Postgres plus dbt plus Metabase. The desktop showcase
must not require Docker, so the embedded profile uses a local read-only data
artifact.

## First Supported Path

- Prebuild the dbt marts from the Maven CRM source data.
- Store the resulting marts in SQLite or DuckDB.
- Point the embedded Python service runtime at the local artifact.
- Keep all service semantics and ANIP contracts unchanged.

## Boundary

Postgres remains the Docker verification path. The desktop app is not allowed
to require a local Postgres server, dbt runtime, or Metabase instance.

## Required Tables

The desktop artifact must include the data needed by:

- `bi_gtm__account_enrichment`
- `bi_gtm__forecast_stage_summary`
- `bi_gtm__pipeline_stage_summary`
- `bi_gtm__product_pipeline`
- `bi_gtm__risk_accounts`
- `bi_gtm__sales_team_performance`
- `bi_gtm__stage_bottlenecks`
- `dim_gtm__accounts`
- `dim_gtm__products`
- `dim_gtm__sales_agents`
- `fct_gtm__opportunities`
- `mart_gtm__account_enrichment`
- `mart_gtm__pipeline_health`

The dbt marts must be prebuilt during release packaging, not at user runtime.
```

- [ ] **Step 3: Run tests**

Run:

```bash
pytest examples/showcase/gtm/desktop/tests/test_desktop_contract.py
```

Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add examples/showcase/gtm/desktop/DATA_PORTABILITY.md examples/showcase/gtm/desktop/tests/test_desktop_contract.py
git commit -m "Document GTM desktop data portability path"
```

---

### Task 5: Add Documentation Links

**Files:**
- Modify: `website/docs/showcases/gtm-agent/overview.md`
- Modify: `website/docs/showcases/gtm-agent/docker-compose.md`

- [ ] **Step 1: Add overview section**

In `website/docs/showcases/gtm-agent/overview.md`, add a section after the opening summary:

```markdown
## Trying the showcase locally

There are two local paths:

- **GTM Agent Desktop** is the installable, non-Docker path for people who want
  to try the agent UI, questions, approvals, and evidence flow without terminal
  setup.
- **Docker Compose** is the full technical verification path with Postgres, dbt,
  Metabase, and generated language stacks.

The desktop app is optimized for product evaluation. Docker Compose is
optimized for architecture inspection and implementation verification.
```

- [ ] **Step 2: Clarify Docker page**

In `website/docs/showcases/gtm-agent/docker-compose.md`, add near the top:

```markdown
If you are evaluating the GTM Agent as a product experience, start with the
desktop app when available. This Docker Compose stack is the full technical
proof: Postgres, dbt, Metabase, generated services, and the agent UI running as
separate containers.
```

- [ ] **Step 3: Run website docs build**

Run:

```bash
cd website && npm run build
```

Expected: Docusaurus build succeeds.

- [ ] **Step 4: Commit**

```bash
git add website/docs/showcases/gtm-agent/overview.md website/docs/showcases/gtm-agent/docker-compose.md
git commit -m "Document GTM desktop showcase path"
```

---

## Self-Review

- Spec coverage: The plan covers non-Docker desktop packaging, embedded sidecar architecture, local API-key setup contract, data portability, and docs positioning.
- Placeholder scan: No task uses open-ended TODO language; each task has concrete file paths, code snippets, commands, and expected output.
- Type consistency: The desktop root is consistently `examples/showcase/gtm/desktop`; the sidecar contract consistently uses `/desktop/health` and `/desktop/config`.

## Execution Recommendation

Start with Tasks 1-3 in this PR. They create the product boundary, Tauri shell, and sidecar contract without pretending the full data migration is already complete. Tasks 4-5 can follow immediately after, or be included if the first PR remains small enough.
