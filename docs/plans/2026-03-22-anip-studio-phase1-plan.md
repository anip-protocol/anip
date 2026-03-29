# ANIP Studio Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ANIP Studio Phase 1 inspection UI — a Vue/Vite single-page app embedded at `/studio` on any ANIP service, with 5 read-only views (Discovery, Manifest, JWKS, Audit, Checkpoints) and a Python FastAPI adapter package.

**Architecture:** Vue 3 + Vite frontend at `studio/`, built to static assets. Python adapter package `anip-studio` at `packages/python/anip-studio/` serves the built assets at `/studio` and provides a bootstrap config endpoint. Showcase apps mount Studio with one line.

**Tech Stack:** Vue 3, Vite, TypeScript. Python, FastAPI, `importlib.resources` for package data serving. Phase 1 uses minimal custom CSS — no Tailwind or CSS framework.

---

## File Structure

```
studio/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.ts
│   ├── App.vue                  # Shell: URL bar + sidebar + router-view
│   ├── router.ts                # Vue Router config (5 routes)
│   ├── api.ts                   # fetch wrappers for ANIP endpoints
│   ├── store.ts                 # reactive state (base URL, bearer token)
│   ├── views/
│   │   ├── DiscoveryView.vue
│   │   ├── ManifestView.vue
│   │   ├── JwksView.vue
│   │   ├── AuditView.vue
│   │   └── CheckpointsView.vue
│   └── components/
│       ├── JsonPanel.vue        # Collapsible JSON tree
│       ├── CapabilityCard.vue   # Single capability with metadata
│       ├── PostureBar.vue       # Trust/disclosure/audit posture bar
│       ├── AuditEntry.vue       # Single audit entry row
│       ├── BearerInput.vue      # Token input for authenticated views
│       └── StatusBadge.vue      # Colored status indicator
├── dist/                        # Built output (checked in)
├── sync.sh                      # Copies dist/ → Python package static/
└── README.md

packages/python/anip-studio/
├── pyproject.toml
├── src/anip_studio/
│   ├── __init__.py              # exports mount_anip_studio
│   ├── routes.py                # FastAPI mount function
│   └── static/                  # Synced from studio/dist/
│       ├── index.html
│       ├── assets/
│       └── ...
└── README.md
```

---

## Task 1: Vue/Vite Project Scaffold

**Files:**
- Create: `studio/package.json`
- Create: `studio/vite.config.ts`
- Create: `studio/tsconfig.json`
- Create: `studio/index.html`
- Create: `studio/src/main.ts`
- Create: `studio/src/App.vue`
- Create: `studio/src/router.ts`
- Create: `studio/src/api.ts`
- Create: `studio/src/store.ts`

- [ ] **Step 1: Initialize the Vue project**

```bash
cd /Users/samirski/Development/ANIP
mkdir -p studio
cd studio
npm create vite@latest . -- --template vue-ts
npm install
npm install vue-router@4
```

This scaffolds the project. Then customize:

- [ ] **Step 2: Configure Vite for /studio base path**

`vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/studio/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
```

The `base: '/studio/'` ensures all asset paths work when served from `/studio/`.

**Phase 1 limitation:** Studio assumes the ANIP service is mounted at the origin root (no path prefix). Services behind a path prefix like `/foo/studio/` are not supported in Phase 1 — this would require prefix-aware config injection, which is a Phase 2 enhancement.

- [ ] **Step 3: Create the API layer**

`src/api.ts` — thin fetch wrappers for all ANIP endpoints:

```ts
export async function fetchDiscovery(baseUrl: string) {
  const res = await fetch(`${baseUrl}/.well-known/anip`)
  if (!res.ok) throw new Error(`Discovery failed: ${res.status}`)
  return res.json()
}

export async function fetchManifest(baseUrl: string) {
  const res = await fetch(`${baseUrl}/anip/manifest`)
  const signature = res.headers.get('X-ANIP-Signature')
  const body = await res.json()
  return { manifest: body, signature }
}

export async function fetchJwks(baseUrl: string) {
  const res = await fetch(`${baseUrl}/.well-known/jwks.json`)
  if (!res.ok) throw new Error(`JWKS failed: ${res.status}`)
  return res.json()
}

export async function fetchAudit(baseUrl: string, bearer: string, filters?: Record<string, string>) {
  const params = new URLSearchParams(filters || {})
  const url = `${baseUrl}/anip/audit${params.toString() ? '?' + params : ''}`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${bearer}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  })
  if (!res.ok) throw new Error(`Audit failed: ${res.status}`)
  return res.json()
}

export async function fetchCheckpoints(baseUrl: string, limit = 10) {
  const res = await fetch(`${baseUrl}/anip/checkpoints?limit=${limit}`)
  if (!res.ok) throw new Error(`Checkpoints failed: ${res.status}`)
  return res.json()
}

export async function fetchCheckpointDetail(baseUrl: string, id: string) {
  const res = await fetch(`${baseUrl}/anip/checkpoints/${id}`)
  if (!res.ok) throw new Error(`Checkpoint detail failed: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 4: Create reactive store**

`src/store.ts` — shared state:

```ts
import { reactive } from 'vue'

export const store = reactive({
  baseUrl: '',
  bearer: '',
  connected: false,
  serviceId: '',
  error: '',
})

export async function initFromConfig() {
  try {
    const res = await fetch('/studio/config.json')
    if (res.ok) {
      const config = await res.json()
      if (config.embedded) {
        store.baseUrl = window.location.origin
      }
      store.serviceId = config.service_id || ''
    }
  } catch {
    // Standalone mode — user enters URL manually
  }
}
```

- [ ] **Step 5: Create router**

`src/router.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import DiscoveryView from './views/DiscoveryView.vue'
import ManifestView from './views/ManifestView.vue'
import JwksView from './views/JwksView.vue'
import AuditView from './views/AuditView.vue'
import CheckpointsView from './views/CheckpointsView.vue'

export const router = createRouter({
  history: createWebHistory('/studio/'),
  routes: [
    { path: '/', name: 'discovery', component: DiscoveryView },
    { path: '/manifest', name: 'manifest', component: ManifestView },
    { path: '/jwks', name: 'jwks', component: JwksView },
    { path: '/audit', name: 'audit', component: AuditView },
    { path: '/checkpoints', name: 'checkpoints', component: CheckpointsView },
  ],
})
```

- [ ] **Step 6: Create App.vue shell**

The app shell with URL bar, sidebar navigation, and router-view. Sidebar highlights the active view. URL bar shows current base URL (editable in standalone mode, read-only in embedded).

- [ ] **Step 7: Create placeholder views**

Create all 5 views as minimal placeholders that show the view name and "Loading..." text. They will be implemented in Task 2.

- [ ] **Step 8: Verify dev server works**

```bash
cd studio && npm run dev
# Open http://localhost:5173/studio/
# Should see the shell with sidebar and Discovery view placeholder
```

- [ ] **Step 9: Commit**

```bash
git add studio/
git commit -m "feat(studio): scaffold Vue/Vite project with router, API layer, and shell"
```

---

## Task 2: Implement the 5 Views

**Files:**
- Create/Modify: `studio/src/views/DiscoveryView.vue`
- Create/Modify: `studio/src/views/ManifestView.vue`
- Create/Modify: `studio/src/views/JwksView.vue`
- Create/Modify: `studio/src/views/AuditView.vue`
- Create/Modify: `studio/src/views/CheckpointsView.vue`
- Create: `studio/src/components/JsonPanel.vue`
- Create: `studio/src/components/CapabilityCard.vue`
- Create: `studio/src/components/PostureBar.vue`
- Create: `studio/src/components/AuditEntry.vue`
- Create: `studio/src/components/BearerInput.vue`
- Create: `studio/src/components/StatusBadge.vue`

Implement each view one at a time. Each view follows the same pattern: fetch data from the API layer, render in a structured panel, include a "Raw JSON" toggle.

- [ ] **Step 1: Create shared components**

- `JsonPanel.vue` — collapsible JSON tree viewer. Takes a `data` prop (any object), renders keys/values with indentation. Toggle between formatted and raw JSON.
- `StatusBadge.vue` — colored dot + label. Green for "healthy"/"signed", yellow for "degraded", red for errors.
- `BearerInput.vue` — text input for bearer token. Stores in `store.bearer`. Shows lock icon when empty.

- [ ] **Step 2: DiscoveryView**

Fetches `GET /.well-known/anip`. Renders:
- Protocol version + compliance badge
- Trust level badge
- Capabilities table (name, side effect, scope, financial flag)
- Posture summary (audit retention, disclosure level, anchoring)
- Endpoints list
- Raw JSON toggle

- [ ] **Step 3: ManifestView**

Fetches `GET /anip/manifest`. Renders:
- Signature header value (displayed, not verified)
- For each capability: `CapabilityCard` component showing name, description, side effect type, cost info, minimum scope, prerequisites, response modes
- Raw JSON toggle

`CapabilityCard.vue` — renders a single capability declaration as a card with:
- Name + description header
- Side effect badge (color-coded: green=read, yellow=write, orange=transactional, red=irreversible)
- Cost info if present
- Scope chips
- Prerequisites list if present

- [ ] **Step 4: JwksView**

Fetches `GET /.well-known/jwks.json`. Renders:
- Table of keys: kid, kty, crv, alg, use
- Each key expandable to show full JWK JSON
- Raw JSON toggle

- [ ] **Step 5: AuditView**

Shows `BearerInput` at top. Once bearer is provided, fetches `POST /anip/audit`.

Renders:
- Filter bar: capability dropdown, since date picker, limit input
- Audit entries table with `AuditEntry` component rows
- Each entry shows: timestamp, capability, success/failure badge, event class, retention tier
- Expandable detail: full entry JSON

`AuditEntry.vue` — single row with:
- Timestamp
- Capability name
- Success/failure StatusBadge
- Event class chip
- Retention tier chip
- Expandable JSON detail

- [ ] **Step 6: CheckpointsView**

Fetches `GET /anip/checkpoints`. Renders:
- Checkpoint list: ID, timestamp, merkle root (truncated), entry count, range
- Click a checkpoint → fetches detail, shows full merkle root, range, signature
- Raw JSON toggle

- [ ] **Step 7: PostureBar component**

`PostureBar.vue` — horizontal bar showing trust/disclosure/audit posture at a glance. Used in DiscoveryView. Shows:
- Trust level (signed/anchored)
- Disclosure level (full/reduced/redacted/policy)
- Audit retention
- Anchoring status

- [ ] **Step 8: Verify all views against the travel showcase**

```bash
# Terminal 1: start the travel showcase
cd examples/showcase/travel && python3 app.py

# Terminal 2: start Studio dev server
cd studio && npm run dev
# Open http://localhost:5173/studio/
# Set URL to http://localhost:8000
# Navigate through all 5 views
```

- [ ] **Step 9: Commit**

```bash
git add studio/src/
git commit -m "feat(studio): implement 5 inspection views with components"
```

---

## Task 3: Build + Sync Script

**Files:**
- Create: `studio/sync.sh`
- Modify: `studio/package.json` (add build script)

- [ ] **Step 1: Build the production bundle**

```bash
cd studio && npm run build
```

Verify `studio/dist/` contains `index.html` and `assets/` directory.

- [ ] **Step 2: Create sync script**

`studio/sync.sh`:
```bash
#!/bin/bash
# Sync built Studio assets to the Python adapter package
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../packages/python/anip-studio/src/anip_studio/static"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SCRIPT_DIR/dist/"* "$DEST/"

echo "Synced studio/dist/ → packages/python/anip-studio/src/anip_studio/static/"
```

```bash
chmod +x studio/sync.sh
```

- [ ] **Step 3: Run the sync**

```bash
cd studio && bash sync.sh
```

- [ ] **Step 4: Commit**

```bash
git add studio/dist/ studio/sync.sh
git commit -m "feat(studio): build production bundle and add sync script"
```

---

## Task 4: Python Adapter Package

**Files:**
- Create: `packages/python/anip-studio/pyproject.toml`
- Create: `packages/python/anip-studio/src/anip_studio/__init__.py`
- Create: `packages/python/anip-studio/src/anip_studio/routes.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "anip-studio"
version = "0.11.0"
description = "ANIP Studio — embedded inspection UI for ANIP services"
requires-python = ">=3.11"
dependencies = [
    "anip-service==0.11.0",
    "fastapi",
]

[tool.hatch.build.targets.wheel]
packages = ["src/anip_studio"]

[tool.hatch.build.targets.wheel.force-include]
"src/anip_studio/static" = "anip_studio/static"
```

- [ ] **Step 2: Create __init__.py**

```python
from .routes import mount_anip_studio

__all__ = ["mount_anip_studio"]
```

- [ ] **Step 3: Create routes.py**

```python
"""ANIP Studio — mount the inspection UI at /studio on a FastAPI app."""
import importlib.resources
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from anip_service import ANIPService


def mount_anip_studio(
    app: FastAPI,
    service: ANIPService,
    prefix: str = "/studio",
) -> None:
    """Mount the ANIP Studio inspection UI.

    Serves the pre-built Vue SPA at {prefix}/ and provides
    a bootstrap config at {prefix}/config.json.
    """
    # Locate the static assets directory (synced from studio/dist/)
    static_dir = Path(__file__).parent / "static"

    if not static_dir.exists():
        import warnings
        warnings.warn(
            "ANIP Studio static assets not found. "
            "Run 'cd studio && npm run build && bash sync.sh' to build them.",
            stacklevel=2,
        )
        return

    # Bootstrap config endpoint (dynamically generated)
    @app.get(f"{prefix}/config.json")
    async def studio_config():
        return JSONResponse({
            "service_id": service.service_id,
            "embedded": True,
        })

    # SPA fallback: any /studio/* path that doesn't match a static file → index.html
    index_html = static_dir / "index.html"

    @app.get(f"{prefix}")
    @app.get(f"{prefix}/")
    async def studio_index():
        return FileResponse(index_html, media_type="text/html")

    # Mount static assets for CSS/JS/etc.
    app.mount(
        f"{prefix}/assets",
        StaticFiles(directory=str(static_dir / "assets")),
        name="studio-assets",
    )

    # SPA catch-all for client-side routing
    @app.get(f"{prefix}/{{path:path}}")
    async def studio_spa_fallback(path: str):
        # Check if the path matches a real file
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(index_html, media_type="text/html")
```

- [ ] **Step 4: Sync static assets**

```bash
cd studio && bash sync.sh
```

- [ ] **Step 5: Install the package**

```bash
pip install --break-system-packages -e packages/python/anip-studio
```

- [ ] **Step 6: Commit**

```bash
git add packages/python/anip-studio/
git commit -m "feat(studio): add Python adapter package (anip-studio)"
```

---

## Task 5: Integrate with Showcase Apps

**Files:**
- Modify: `examples/showcase/travel/app.py`
- Modify: `examples/showcase/travel/requirements.txt`
- Modify: `examples/showcase/finance/app.py`
- Modify: `examples/showcase/finance/requirements.txt`
- Modify: `examples/showcase/devops/app.py`
- Modify: `examples/showcase/devops/requirements.txt`

- [ ] **Step 1: Add Studio to travel showcase**

In `examples/showcase/travel/app.py`, add:
```python
from anip_studio import mount_anip_studio
# After other mounts:
mount_anip_studio(app, service)
```

In `requirements.txt`, add:
```
-e ../../../packages/python/anip-studio
```

- [ ] **Step 2: Add Studio to finance and devops showcases**

Same pattern for both.

- [ ] **Step 3: Verify Studio loads on all three showcases**

```bash
cd examples/showcase/travel && python3 app.py &
sleep 3
curl -sf http://localhost:8000/studio/ | head -c 200
echo ""
curl -sf http://localhost:8000/studio/config.json
echo ""
kill %1
```

Repeat for finance and devops.

- [ ] **Step 4: Commit**

```bash
git add examples/showcase/
git commit -m "feat(studio): mount Studio on all three showcase apps"
```

---

## Task 6: End-to-End Verification + PR

- [ ] **Step 1: Start a showcase and verify all 5 views in the browser**

```bash
cd examples/showcase/travel && python3 app.py
# Open http://localhost:8000/studio/
# Verify:
# - Discovery view loads and shows capabilities
# - Manifest view shows capability cards with side effects
# - JWKS view shows public keys
# - Audit view accepts a bearer token and shows entries
# - Checkpoints view shows checkpoint list (may be empty on fresh start)
```

- [ ] **Step 2: Test against finance (anchored trust, disclosure policy)**

```bash
cd examples/showcase/finance && python3 app.py
# Open http://localhost:8000/studio/
# Verify Discovery shows trust_level: anchored and disclosure_level: policy
```

- [ ] **Step 3: Run conformance to ensure Studio mount doesn't break anything**

```bash
cd examples/showcase/travel && python3 app.py &
sleep 3
pytest conformance/ --base-url=http://localhost:8000 --bootstrap-bearer=demo-human-key --sample-inputs=conformance/samples/flight-service.json -q
kill %1
```

Expected: 43 passed, 1 skipped (Studio routes don't interfere with ANIP protocol routes)

- [ ] **Step 4: Update release workflow**

Add `anip-studio` to the Python package validation and publish loops in `.github/workflows/release.yml`:

- In the Python validation step (`Validate Python package versions`), add `anip-studio` to the package list
- In the Python publish step (`Publish in dependency order`), add `publish_or_skip anip-studio` after `anip-graphql`

- [ ] **Step 5: Create README**

`studio/README.md` explaining what Studio is, how to build it, how to embed it.

- [ ] **Step 6: Push and create PR**

```bash
git push -u origin feat/anip-studio
gh pr create --title "feat: add ANIP Studio Phase 1 — embedded inspection UI"
```
