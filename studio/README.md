# ANIP Studio

Studio is two things in one source tree:

- **Inspect** — a small tool that connects to a running ANIP service and shows
  you what the service declares and what it has done. This is the supported
  part of Studio, and the part that ships inside the runtime packages.
- **Design** — a large workbench for designing ANIP services before they exist.
  **Design is experimental.** See [Design (experimental)](#design-experimental)
  for what that means before you rely on it.

## Inspect

Point Inspect at an ANIP service and it reads the service's own protocol
endpoints. It needs no database and no Studio backend.

| View | What it shows |
|------|---------------|
| Discovery | `/.well-known/anip`: protocol version, compliance, trust level, posture, each capability's side effect, scope, financial flag and contract version, and the endpoint map |
| Manifest | Full capability declarations (inputs, output, side effect, cost, bindings), manifest metadata, service identity and the manifest signature |
| JWKS | The service's public signing keys |
| Audit | Audit entries with filters (needs a delegation token) |
| Approvals | Lists and approves pending approval requests from the service's own approval routes (default `/approvals`, needs a bearer credential that those routes accept). These routes are service-specific, not ANIP protocol endpoints, so the view is empty for a service that does not have them |
| Checkpoints | Merkle checkpoints and their detail |
| Invoke | Invoke a capability from a form built from its declared inputs, with a permissions check and structured failures (needs a delegation token) |

The side-effect badge is the quickest way to see which capabilities are safe to
try: `read` is green, `write` and `transactional` are amber, `irreversible` is
red. A capability whose side effect the service did not declare shows as
`unknown`, never as `read`.

### Use it embedded in a service

Each runtime has a `*-studio` package that carries a pre-built Inspect bundle
and serves it at `/studio` on the service itself. Embedded Inspect connects to
the service it is mounted on, so there is nothing to configure.

| Runtime | Package | Mount call |
|---------|---------|------------|
| Python (FastAPI) | `anip-studio` | `mount_anip_studio(app, service)` |
| TypeScript (Hono) | `@anip-dev/studio` | `mountAnipStudio(app, service)` |
| Go (`net/http`) | `packages/go/studioapi` | `studioapi.MountANIPStudio(mux, serviceID)` |
| Java (Spring) | `anip-studio` | register `new AnipStudioController(serviceId)` as a bean |
| C# (ASP.NET Core) | `Anip.Studio` | `app.MapAnipStudio(serviceId)` |

```python
# In your ANIP FastAPI app:
from anip_studio import mount_anip_studio

mount_anip_studio(app, service)
# Start the service, then open http://localhost:9100/studio/
```

Audit, Invoke and the permissions check in Invoke need an **ANIP delegation
token** (a JWT), pasted into the Authentication field of the view. Inspect does
not exchange an API key for a token: with an API key these views show the
service's `401 invalid_token` response. Issue a token from the service first.
For the Python flight example (`examples/anip`, bootstrap key
`demo-human-key`):

```bash
curl -s -X POST http://localhost:9100/anip/tokens \
  -H "Authorization: Bearer demo-human-key" \
  -H "Content-Type: application/json" \
  -d '{"scope": ["travel.search"], "capability": "search_flights"}'
# Paste the "token" value from the response into Inspect.
```

The embedded bundle contains Inspect only. It has no Design routes and does not
show the Design entry on the home screen.

### Use it standalone

Run Inspect from this directory and connect it to any ANIP service by URL:

```bash
cd studio
npm ci
VITE_INSPECT_ONLY=true npm run dev
# Open http://localhost:5173/studio/inspect/discovery?connect=http://localhost:9100
```

`?connect=<service-url>` connects on load; without it, type the service URL
into the header and press Connect.

Standalone Inspect runs at a different origin than the service, so the service
must allow cross-origin requests and expose the manifest signature header:

```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your Studio origin
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ANIP-Signature"],
)
```

Embedded Inspect shares the service's origin and needs none of this.

### Rebuilding the embedded bundle

`bash studio/sync.sh` builds the Inspect-only bundle and copies it into all
five runtime packages, where it is committed (Go needs the files on disk for
`go:embed`):

- `packages/python/anip-studio/src/anip_studio/static/`
- `packages/typescript/studio/static/`
- `packages/go/studioapi/static/`
- `packages/java/anip-studio/src/main/resources/studio/`
- `packages/csharp/src/Anip.Studio/static/`

The bundle compiles `packages/typescript/client` and `packages/typescript/vue`
from source. After changing those packages or anything under `studio/src`, run
`bash studio/sync.sh` and commit all five copies. CI rebuilds the bundle and
fails if any copy differs.

## Design (experimental)

Design is a workbench for product and developer design of ANIP services:
source documents, requirements, scenarios, service shapes, evaluation,
package and template publishing, and read-only showcase browsing. It is a much
larger body of code than Inspect and is not held to the same standard.

Known limits:

- **Experimental.** It can change or break between releases. Development
  effort is going into Inspect, not Design.
- **Needs its own backend.** Design does not work in the embedded bundle. It
  needs the Studio API (`studio/server`) with Postgres (Docker Compose) or
  SQLite (desktop app).
- **The SQLite desktop backend is thinly tested.** CI runs the SQLite tests in
  `studio/server_sqlite_tests` and a Docker Compose smoke test. The larger
  server suite in `studio/server/test_*.py` needs Postgres and does not run in
  CI. "Create Initial Project Setup" failed on SQLite until it got a SQLite
  test.
- **Known SQLite gaps.** REST endpoints return timestamps without a UTC offset
  on SQLite, so a browser reads them as local time. Creating a data-access or
  application-integration draft with an ID that already exists returns a
  server error instead of `409 Conflict`.

### Run it with Docker Compose

```bash
cd studio
docker compose up --build

# Open http://localhost:8080/design
# API is available at http://localhost:8100
```

The stack is Postgres, the Studio API and the Studio web UI. The web UI
listens on host port 8080 and the API on 8100 unless you set `STUDIO_WEB_PORT`
and `STUDIO_API_PORT`.

To run a published Studio release image instead of tagging local builds as `local`, set
`STUDIO_IMAGE_TAG` before starting Compose. This is the Studio image version, not
the ANIP protocol version; Studio remains compatible with ANIP `0.24`.

```bash
STUDIO_IMAGE_TAG=0.9.0 docker compose up
```

To force a fresh pull of the published release images:

```bash
STUDIO_IMAGE_TAG=0.9.0 docker compose pull
STUDIO_IMAGE_TAG=0.9.0 docker compose up
```

Useful environment switches:

```bash
# Restore canonical published showcase snapshots into one editable workspace.
STUDIO_SEED_SHOWCASES=1 docker compose up --build

# Host a read-only Studio demo. Unsafe HTTP methods are blocked at the API
# boundary; only GET, HEAD, and OPTIONS remain available.
STUDIO_IMAGE_TAG=0.9.0 STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up

# Optionally switch to a read-only database role after startup migrations,
# vocabulary load, and showcase seeding complete.
STUDIO_IMAGE_TAG=0.9.0 \
STUDIO_READ_ONLY=1 \
STUDIO_READ_ONLY_DATABASE_URL=postgresql://anip_readonly:anip_readonly@studio-db:5432/anip_studio \
docker compose up

# Avoid local port collisions.
STUDIO_WEB_PORT=8180 STUDIO_API_PORT=8110 docker compose up --build
```

To run the local release smoke in the same read-only, preseeded posture:

```bash
studio/scripts/smoke-compose.sh
```

The smoke stack removes its Compose volume before each run, verifies that the UI
and API are reachable, confirms showcase projects were seeded, verifies
read-only mode is active, and confirms representative mutation routes return
`403`. Set `STUDIO_SMOKE_KEEP_STACK=1` to leave the stack running for manual
inspection. Set `STUDIO_SMOKE_SKIP_BUILD=1` to reuse existing local
`anipprotocol/studio-api:local` and `anipprotocol/studio-web:local` images
during repeat runs.

Published images are split by responsibility:

- `anipprotocol/studio-api:<version>` — FastAPI server, project store, assistant/workbench routes.
- `anipprotocol/studio-web:<version>` — nginx web UI that proxies to `studio-api`.
- `anipprotocol/studio:<version>` — compatibility alias for the web UI image.

### Desktop mode

To run the Studio API locally in desktop SQLite mode without Docker or
Postgres:

```bash
studio/scripts/start-desktop-api.sh
```

The launcher starts only the FastAPI server at
`http://127.0.0.1:${STUDIO_DESKTOP_API_PORT:-8100}`. It defaults to
`STUDIO_MODE=desktop`, `STUDIO_DB_BACKEND=sqlite`, seeds showcase data, enables
migrations, and writes SQLite data to
`${ANIP_STUDIO_DESKTOP_DATA_DIR:-~/.anip/studio}/studio.sqlite` unless
`STUDIO_SQLITE_PATH` is set.

To build the macOS desktop app shell with the bundled Studio API sidecar:

```bash
./.venv/bin/python -m pip install -r studio/server/desktop-build-requirements.txt
npm --prefix studio install
npm --prefix studio run desktop:build
```

The desktop app bundles the static Studio UI and a frozen Studio API sidecar.
On launch, it starts the API on `127.0.0.1:8100`, uses the same SQLite data
location as `start-desktop-api.sh`, and stores local project data under
`~/.anip/studio` by default.

## Development

```bash
cd studio
npm ci
npm run dev      # Dev server at http://localhost:5173/studio/ (Inspect and Design)
npx vue-tsc -b   # Type check
npm test         # Run vitest suite
npm run build    # Type check, then production build to dist/
bash sync.sh     # Build Inspect-only and sync it to all five runtime packages
```

### Studio Assistant providers

The Studio assistant can stay deterministic, or it can use a configured model
provider for interpretation and explanation while keeping validation and
evaluation deterministic.

Supported providers:

- `deterministic` (default)
- `openai`
- `anthropic`
- `ollama`

Configuration is environment-driven:

```bash
export STUDIO_ASSISTANT_PROVIDER=openai
export STUDIO_ASSISTANT_MODEL=gpt-5.4
export OPENAI_API_KEY=...

# Optional overrides
export STUDIO_ASSISTANT_BASE_URL=https://api.openai.com/v1
export STUDIO_ASSISTANT_TEMPERATURE=0.2
export STUDIO_ASSISTANT_TIMEOUT_SECONDS=20
export STUDIO_ASSISTANT_STRICT=false
```

Examples:

```bash
# OpenAI
export STUDIO_ASSISTANT_PROVIDER=openai
export STUDIO_ASSISTANT_MODEL=gpt-5.4
export OPENAI_API_KEY=...

# Anthropic
export STUDIO_ASSISTANT_PROVIDER=anthropic
export STUDIO_ASSISTANT_MODEL=claude-sonnet-4-5
export ANTHROPIC_API_KEY=...

# Ollama using the OpenAI-compatible endpoint
export STUDIO_ASSISTANT_PROVIDER=ollama
export STUDIO_ASSISTANT_MODEL=qwen2.5:14b
export STUDIO_ASSISTANT_BASE_URL=http://127.0.0.1:11434/v1
```

If no provider is configured, or the configured provider fails and
`STUDIO_ASSISTANT_STRICT` is not enabled, Studio falls back to the deterministic
assistant path.

### Registry trust policy

Studio Registry verification runs the verifier and persists its JSON result
as provenance. Local development accepts any Registry signing mode by default.
The Studio header Settings dialog can store local Registry URL, required mode,
trusted key id, and the remote publish token alongside LLM configuration.
Environment variables override and lock the corresponding fields.
For production Studio deployments, set a required Registry signing mode and,
optionally, a trusted receipt signing key id and publish token:

```bash
export STUDIO_REGISTRY_URL=https://registry.example.com
export STUDIO_REGISTRY_REQUIRED_MODE=production
export STUDIO_REGISTRY_TRUSTED_KEY_ID=registry-prod-2026-04
export STUDIO_REGISTRY_PUBLISH_TOKEN=<registry-publish-token>
```

If `STUDIO_REGISTRY_REQUIRED_MODE` is omitted and `STUDIO_MODE=production`
or `APP_ENV=production` or `ENVIRONMENT=production`, Studio requires
`production` Registry signing mode automatically.

Trust policy mismatches are saved as failed verifier provenance so the project
history shows why a Registry package was rejected.

## Build Configuration

The base path is controlled by the `VITE_BASE_PATH` environment variable:

| Target | Value | Command |
|--------|-------|---------|
| Embedded | `/studio/` | `bash sync.sh` (sets it automatically) |
| Full product web image | `/` | Docker build sets it automatically |
| Dev server | `/studio/` | `npm run dev` (uses default) |

## Architecture

- Vue 3 + Vite + TypeScript frontend
- Builds to static assets (no runtime Node dependency)
- **Embedded:** each runtime's `*-studio` package serves the Inspect-only assets at `/studio` with `config.json` marking `embedded: true`
- **Full product:** nginx serves assets at `/` with Design routes under `/design` and same-origin API proxying to `studio-api`
- Full-product `config.json` marks `embedded: false` because the Studio web origin is not itself an ANIP service root; Invoke & Inspect requires an explicit ANIP service URL or `?connect=<service-url>`
