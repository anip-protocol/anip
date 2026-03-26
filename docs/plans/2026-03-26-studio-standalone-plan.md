# ANIP Studio Standalone — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package ANIP Studio as a standalone Docker image (nginx + static assets) deployable at `studio.anip.dev` or locally via `docker run`.

**Architecture:** Parameterize the Vite base path via `VITE_BASE_PATH` env var (`/studio/` for embedded, `/` for standalone). Multi-stage Docker build: node:22-alpine builds the app, nginx:alpine serves it with SPA fallback and cache headers. CI smoke-tests the Docker build.

**Tech Stack:** Vue 3, Vite, nginx, Docker

**Spec:** `docs/specs/2026-03-26-studio-standalone-design.md`

---

## File Structure

```
studio/
├── vite.config.ts              # MODIFY: base from VITE_BASE_PATH with normalization
├── src/router.ts               # MODIFY: history base from import.meta.env.VITE_BASE_PATH
├── src/store.ts                # MODIFY: config fetch uses import.meta.env.BASE_URL
├── sync.sh                     # MODIFY: run build with VITE_BASE_PATH=/studio/ then copy
├── Dockerfile                  # CREATE: multi-stage build
├── nginx.conf                  # CREATE: SPA config with cache headers
├── standalone-config.json      # CREATE: { "embedded": false }
├── .dockerignore               # CREATE: exclude non-build files
└── README.md                   # MODIFY: add standalone/Docker docs

.github/workflows/ci-studio.yml # MODIFY: add Docker build smoke test + VITE_BASE_PATH on build step
```

---

## Task 1: Build Parameterization

**Files:**
- Modify: `studio/vite.config.ts`
- Modify: `studio/src/router.ts`
- Modify: `studio/src/store.ts`

- [ ] **Step 1: Update `vite.config.ts`**

Replace the hardcoded `base: '/studio/'` with a parameterized version:

```typescript
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

export default defineConfig({
  plugins: [vue()],
  base: normalizeBase(process.env.VITE_BASE_PATH ?? '/studio/'),
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
```

- [ ] **Step 2: Update `router.ts`**

Replace the hardcoded `'/studio/'` in `createWebHistory`:

```typescript
import { createRouter, createWebHistory } from 'vue-router'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

const routes = [
  {
    path: '/',
    name: 'discovery',
    component: () => import('./views/DiscoveryView.vue'),
  },
  {
    path: '/manifest',
    name: 'manifest',
    component: () => import('./views/ManifestView.vue'),
  },
  {
    path: '/jwks',
    name: 'jwks',
    component: () => import('./views/JwksView.vue'),
  },
  {
    path: '/audit',
    name: 'audit',
    component: () => import('./views/AuditView.vue'),
  },
  {
    path: '/checkpoints',
    name: 'checkpoints',
    component: () => import('./views/CheckpointsView.vue'),
  },
  {
    path: '/invoke/:capability?',
    name: 'invoke',
    component: () => import('./views/InvokeView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(normalizeBase(import.meta.env.VITE_BASE_PATH || '/studio/')),
  routes,
})
```

- [ ] **Step 3: Update `store.ts` config fetch**

Replace `fetch('./config.json')` with a base-aware absolute path:

```typescript
import { reactive } from 'vue'

export const store = reactive({
  baseUrl: '',
  bearer: '',
  connected: false,
  serviceId: '',
  error: '',
  loading: false,
})

export async function initFromConfig() {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}config.json`)
    if (res.ok) {
      const config = await res.json()
      if (config.embedded) {
        store.baseUrl = window.location.origin
      }
      store.serviceId = config.service_id || ''

      // Auto-connect in embedded mode
      if (store.baseUrl) {
        try {
          const disco = await fetch(`${store.baseUrl}/.well-known/anip`)
          if (disco.ok) {
            store.connected = true
          }
        } catch {
          // Service not reachable — user can connect manually
        }
      }
    }
  } catch {
    // Standalone mode — config.json not available
  }
}
```

- [ ] **Step 4: Verify build with default (embedded) base path**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit`
Expected: no type errors

Run: `cd /Users/samirski/Development/ANIP/studio && npx vite build`
Expected: build succeeds, asset paths in `dist/index.html` prefixed with `/studio/`

- [ ] **Step 5: Verify build with standalone base path**

Run: `cd /Users/samirski/Development/ANIP/studio && VITE_BASE_PATH=/ npx vite build`
Expected: build succeeds, asset paths in `dist/index.html` prefixed with `/`

- [ ] **Step 6: Run existing tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run`
Expected: all 55 tests pass

- [ ] **Step 7: Commit**

```bash
git add studio/vite.config.ts studio/src/router.ts studio/src/store.ts
git commit -m "feat(studio): parameterize base path via VITE_BASE_PATH"
```

---

## Task 2: Update sync.sh and CI Build Step

**Files:**
- Modify: `studio/sync.sh`
- Modify: `.github/workflows/ci-studio.yml`

- [ ] **Step 1: Update `sync.sh` to build and sync**

Replace the entire file:

```bash
#!/bin/bash
# Build Studio for embedded mode and sync assets to the Python adapter package
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../packages/python/anip-studio/src/anip_studio/static"

# Build with embedded base path
echo "Building Studio with VITE_BASE_PATH=/studio/ ..."
cd "$SCRIPT_DIR"
VITE_BASE_PATH=/studio/ npx vite build

# Sync to Python adapter
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SCRIPT_DIR/dist/"* "$DEST/"

echo "Synced studio/dist/ → packages/python/anip-studio/src/anip_studio/static/"
```

- [ ] **Step 2: Update CI build step to set `VITE_BASE_PATH`**

In `.github/workflows/ci-studio.yml`:

1. **Remove** the standalone "Build" step entirely (the one that runs `npx vite build`). The `sync.sh` step below now handles the build.

2. **Replace** the "Verify synced assets" step with one that builds via `sync.sh` and checks for drift:

```yaml
      - name: Build and verify synced assets
        run: |
          bash studio/sync.sh
          if [ -n "$(git status --porcelain packages/python/anip-studio/src/anip_studio/static/)" ]; then
            echo "ERROR: Studio assets are stale. Run 'cd studio && bash sync.sh' and commit the result."
            git diff --stat packages/python/anip-studio/src/anip_studio/static/
            exit 1
          fi
          echo "Studio assets are in sync."
```

This avoids a double-build — `sync.sh` builds with `VITE_BASE_PATH=/studio/` and then copies.

- [ ] **Step 3: Commit**

```bash
git add studio/sync.sh .github/workflows/ci-studio.yml
git commit -m "build(studio): sync.sh now builds with VITE_BASE_PATH=/studio/"
```

---

## Task 3: Docker Packaging

**Files:**
- Create: `studio/Dockerfile`
- Create: `studio/nginx.conf`
- Create: `studio/standalone-config.json`
- Create: `studio/.dockerignore`

- [ ] **Step 1: Create `studio/standalone-config.json`**

```json
{
  "embedded": false
}
```

- [ ] **Step 2: Create `studio/.dockerignore`**

```
node_modules
dist
*.png
*.md
.superpowers
.vscode
.gitignore
src/__tests__
```

- [ ] **Step 3: Create `studio/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Enable gzip
    gzip on;
    gzip_types text/html text/css application/javascript application/json;
    gzip_min_length 256;

    # Hashed assets — cache forever
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # Mutable config — never cache
    location = /config.json {
        add_header Cache-Control "no-cache";
    }

    # SPA fallback — index.html is also no-cache
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }
}
```

- [ ] **Step 4: Create `studio/Dockerfile`**

```dockerfile
# --- Build stage ---
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY src/ src/
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./

ENV VITE_BASE_PATH=/
RUN npx vite build

# --- Serve stage ---
FROM nginx:alpine

COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY standalone-config.json /usr/share/nginx/html/config.json

EXPOSE 80
```

- [ ] **Step 5: Build the Docker image**

Run: `cd /Users/samirski/Development/ANIP && docker build -t anip-studio studio/`
Expected: builds successfully, image ~25MB

- [ ] **Step 6: Test the Docker image**

Run: `docker run -d --name anip-studio-test -p 3000:80 anip-studio`

Verify with curl:
```bash
# Index page loads
curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/
# Expected: 200

# Config.json is served
curl -s http://localhost:3000/config.json
# Expected: {"embedded":false}

# SPA fallback works for deep routes
curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/invoke/search_flights
# Expected: 200

# Assets have immutable cache headers (grab a real asset path from index.html)
ASSET=$(curl -s http://localhost:3000/ | grep -oE '/assets/[^"]+\.js' | head -1)
curl -sI "http://localhost:3000$ASSET" | grep -i cache-control
# Expected: Cache-Control: public, max-age=31536000, immutable

# config.json has no-cache headers
curl -sI http://localhost:3000/config.json | grep -i cache-control
# Expected: Cache-Control: no-cache
```

Clean up:
```bash
docker stop anip-studio-test && docker rm anip-studio-test
```

- [ ] **Step 7: Commit**

```bash
git add studio/Dockerfile studio/nginx.conf studio/standalone-config.json studio/.dockerignore
git commit -m "feat(studio): add Dockerfile and nginx config for standalone deployment"
```

---

## Task 4: CI Smoke Test

**Files:**
- Modify: `.github/workflows/ci-studio.yml`

- [ ] **Step 1: Add Docker build smoke test to `ci-studio.yml`**

Append a new step after "Verify synced assets are up to date":

```yaml
      - name: Docker build smoke test
        run: docker build -t anip-studio-test studio/
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci-studio.yml
git commit -m "ci(studio): add Docker build smoke test"
```

---

## Task 5: README and Sync Verification

**Files:**
- Modify: `studio/README.md`

- [ ] **Step 1: Update `studio/README.md`**

Replace the entire file with the content below. Note: inner code blocks use indented (4-space) fencing to avoid fence nesting issues when reading this plan.

**README sections to include (in order):**

1. **Title & intro:** "ANIP Studio" — inspection and invocation UI, two modes (embedded, standalone)

2. **Embedded Mode** — Python example:

        # In your ANIP FastAPI app:
        from anip_studio import mount_anip_studio
        mount_anip_studio(app, service)
        # → Open http://localhost:9100/studio/

3. **Standalone Mode (Docker):**

        # Build the image
        docker build -t anip-studio studio/
        # Run locally
        docker run -p 3000:80 anip-studio
        # Open http://localhost:3000
        # Enter your ANIP service URL in the connect bar

4. **Views table** — 6 views: Discovery, Manifest, JWKS, Audit, Checkpoints, Invoke

5. **Development:**

        cd studio
        npm install
        npm run dev    # Dev server at http://localhost:5173/studio/
        npm run build  # Production build to dist/
        npm test       # Run vitest suite
        bash sync.sh   # Build for embedded mode and sync to Python package

6. **Build Configuration** — table of `VITE_BASE_PATH` values:
   - Embedded: `/studio/` via `bash sync.sh`
   - Standalone: `/` via `VITE_BASE_PATH=/ npx vite build`
   - Dev server: `/studio/` (default)

7. **Architecture** — Vue 3 + Vite + TS, static assets, embedded vs standalone config.json, connect bar

8. **CORS Requirement** — standalone Studio runs at a different origin; services must enable CORS. Show the `CORSMiddleware` snippet (same as travel showcase). Note: not needed in embedded mode.

The implementer should write this as a standard markdown file with proper fenced code blocks for the Python, bash, and nginx examples.

- [ ] **Step 2: Rebuild and re-sync embedded assets**

Since `sync.sh` now builds with `VITE_BASE_PATH=/studio/`, run it:

```bash
cd /Users/samirski/Development/ANIP && bash studio/sync.sh
```

Expected: `Synced studio/dist/ → packages/python/anip-studio/src/anip_studio/static/`

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run`
Expected: all 55 tests pass

- [ ] **Step 4: Commit**

```bash
git add studio/README.md packages/python/anip-studio/src/anip_studio/static/
git commit -m "docs(studio): document embedded and standalone deployment modes"
```

---

## Task 6: CORS for Standalone Access

**Files:**
- Modify: `examples/showcase/finance/app.py`
- Modify: `examples/showcase/devops/app.py`

Standalone Studio runs in the browser at a different origin than the ANIP service it connects to (e.g., `localhost:3000` calling `localhost:9100`). This requires the ANIP service to allow cross-origin requests. The travel showcase already has CORS enabled; the finance and devops showcases do not.

- [ ] **Step 1: Add CORS middleware to finance showcase**

In `examples/showcase/finance/app.py`, add after the `app = FastAPI(...)` line:

```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ANIP-Signature"],
)
```

Check if `CORSMiddleware` is already imported — if not, add the import. Follow the same pattern as `examples/showcase/travel/app.py:29-34`.

- [ ] **Step 2: Add CORS middleware to devops showcase**

Same change in `examples/showcase/devops/app.py`.

- [ ] **Step 3: Verify showcases still start**

```bash
cd /Users/samirski/Development/ANIP/examples/showcase/finance && python app.py &
FINANCE_PID=$!
sleep 3
curl -s -o /dev/null -w '%{http_code}' http://localhost:9100/.well-known/anip
# Expected: 200
kill $FINANCE_PID 2>/dev/null || true

cd /Users/samirski/Development/ANIP/examples/showcase/devops && python app.py &
DEVOPS_PID=$!
sleep 3
curl -s -o /dev/null -w '%{http_code}' http://localhost:9100/.well-known/anip
# Expected: 200
kill $DEVOPS_PID 2>/dev/null || true
```

- [ ] **Step 4: Commit**

```bash
git add examples/showcase/finance/app.py examples/showcase/devops/app.py
git commit -m "fix(showcase): enable CORS on finance and devops showcases for standalone Studio"
```
