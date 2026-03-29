# ANIP Studio Standalone — Design Spec

## Purpose

Package ANIP Studio as a standalone Docker image so it can be deployed independently — both as a hosted service at `studio.anip.dev` and as a self-hosted container for local evaluation. Today Studio only runs embedded inside a Python ANIP service at `/studio`. This spec adds a second deployment mode without changing the embedded path.

## Scope

**v1 includes:**

1. Build-time base path parameterization (`VITE_BASE_PATH`)
2. Dockerfile with multi-stage build (node + nginx)
3. nginx config with SPA fallback and cache headers
4. Standalone `config.json` with `embedded: false`
5. `.dockerignore` for clean build context
6. CI smoke test (Docker build verification)
7. Studio README documenting both deployment modes

**v1 does not include:**

- Docker image registry publishing or release automation
- HTTPS termination (handled by external ingress/LB/CDN)
- Runtime configuration injection (e.g., default URL via env var) — future enhancement
- Health endpoint — future enhancement if needed for hosting checks

## Build Parameterization

### `VITE_BASE_PATH`

A build-time environment variable that controls the base path for the Vue app, its router, and all asset URLs.

| Target | Value | Set by |
|--------|-------|--------|
| Embedded (Python adapter) | `/studio/` | `sync.sh` |
| Standalone (Docker) | `/` | `Dockerfile` |

The variable is read in two places:

**`vite.config.ts`** — controls asset URL prefixes:
```typescript
base: process.env.VITE_BASE_PATH ?? '/studio/'
```

**`router.ts`** — controls client-side routing base:
```typescript
createWebHistory(import.meta.env.VITE_BASE_PATH || '/studio/')
```

Both use `/studio/` as the default so the existing build behavior is unchanged if the variable is unset.

### Trailing-slash normalization

The base path must always end with `/`. A small normalization is applied in both locations so that passing `/studio` (without trailing slash) does not create subtle routing bugs:
```typescript
function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}
```

The `normalizeBase` helper is inlined in each file rather than shared — `vite.config.ts` runs in Node while `router.ts` runs in the browser, so a shared module would add unnecessary complexity.

Vite automatically applies the `base` value to `index.html` asset references during build. No manual changes to `index.html` are needed.

### `sync.sh`

Currently `sync.sh` only copies `dist/` to the Python adapter — it does not run the build. Updated to also run the build with `VITE_BASE_PATH=/studio/` explicitly set, making it a single command for the embedded packaging flow:

```bash
VITE_BASE_PATH=/studio/ npx vite build
# then copy dist/ to Python adapter
```

This keeps the embedded build deterministic regardless of shell environment. The CI workflow's separate build step should also set `VITE_BASE_PATH=/studio/` explicitly.

## Docker Image

### Architecture

Multi-stage build:

1. **Build stage** (`node:22-alpine`): Install dependencies, build with `VITE_BASE_PATH=/`
2. **Serve stage** (`nginx:alpine`): Copy built assets + nginx config + standalone config.json

### Dockerfile location

`studio/Dockerfile`

### nginx config

`studio/nginx.conf`:

- Listen on port 80
- Serve static files from `/usr/share/nginx/html`
- SPA fallback: `try_files $uri $uri/ /index.html`
- Cache headers:
  - `/assets/*` (hashed filenames): `Cache-Control: public, max-age=31536000, immutable`
  - `index.html` and `config.json`: `Cache-Control: no-cache`
- Gzip enabled for JS, CSS, JSON, HTML

Location block structure:
```nginx
location /assets/ {
    # Hashed filenames — cache forever
    add_header Cache-Control "public, max-age=31536000, immutable";
}

location = /config.json {
    # Mutable config — never cache
    add_header Cache-Control "no-cache";
}

location / {
    # SPA fallback — index.html is also no-cache
    try_files $uri $uri/ /index.html;
    add_header Cache-Control "no-cache";
}
```

### Standalone config

`studio/standalone-config.json`:
```json
{
  "embedded": false
}
```

Copied into the nginx html root as `config.json` during the Docker build. The existing `initFromConfig()` in `store.ts` reads this file — when `embedded` is `false`, the app shows the URL connect bar and waits for the user to connect manually.

This file is extensible. Future additions might include `default_url`, `label`, or feature flags.

**`store.ts` requires a small change.** The existing `fetch('./config.json')` is a relative URL that resolves against the current route path, not the app root. On a nested route like `/invoke/search_flights`, it would resolve to `/invoke/config.json` which does not exist. Fix by using Vite's `import.meta.env.BASE_URL` to build an absolute path:

```typescript
const res = await fetch(`${import.meta.env.BASE_URL}config.json`)
```

`BASE_URL` is automatically set by Vite to match the `base` config (e.g., `/studio/` or `/`), so this resolves correctly under both deployment modes and all route depths.

### `.dockerignore`

```
node_modules
dist
*.png
*.md
.superpowers
.vscode
.gitignore
tsconfig*.json
src/__tests__
```

Keeps the build context small — only source files needed for the Vite build are sent to the Docker daemon.

### Usage

```bash
# Build the image
docker build -t anip-studio studio/

# Run locally
docker run -p 3000:8080 anip-studio

# Open http://localhost:3000
# Enter your ANIP service URL in the connect bar
```

### Image size

~25MB (nginx:alpine base + static Vue assets).

## CI

Add a Docker build smoke test to the existing `ci-studio.yml` workflow. This verifies the Dockerfile, nginx config, and build context stay valid without adding publish automation.

The smoke test runs after the existing build step and uses the same trigger paths (`studio/**`, `packages/python/anip-studio/**`).

No image push. No registry. Just `docker build` to catch drift.

The smoke test is a new step appended to the existing `build` job in `ci-studio.yml` (after the "Verify synced assets" step), running `docker build -t anip-studio-test studio/` from the repo root. This avoids adding a new job or re-checking out the code.

## Files

### New files
- `studio/Dockerfile` — multi-stage build
- `studio/nginx.conf` — SPA-aware nginx config with cache headers
- `studio/standalone-config.json` — `{ "embedded": false }`
- `studio/.dockerignore` — exclude node_modules, dist, tests, docs

### Modified files
- `studio/vite.config.ts` — `base` from `VITE_BASE_PATH` with normalization
- `studio/src/router.ts` — history base from `import.meta.env.VITE_BASE_PATH` with normalization
- `studio/src/store.ts` — config fetch uses `import.meta.env.BASE_URL` instead of relative path
- `studio/sync.sh` — run build with `VITE_BASE_PATH=/studio/` then copy
- `studio/README.md` — add standalone/Docker deployment documentation
- `.github/workflows/ci-studio.yml` — add Docker build smoke test step

## What This Does Not Cover

- Registry publishing or release automation
- HTTPS / TLS termination
- Runtime env var injection (e.g., `ANIP_DEFAULT_URL`)
- Health check endpoint
- CDN or edge caching configuration for `studio.anip.dev`
- Authentication or access control for the Studio UI itself
