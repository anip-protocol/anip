# ANIP Studio

ANIP Studio is the design, review, packaging, and inspection workbench for ANIP
projects. It supports PM/business design, developer design, package/template
publishing, generated-service validation, read-only showcase browsing, and
service inspection.

It has two operating shapes:

- **Full product** — Docker Compose stack with Postgres, Studio API, and Studio web UI.
- **Embedded/inspection UI** — mounted inside an ANIP service for service discovery and invocation.

## Embedded Mode

```python
# In your ANIP FastAPI app:
from anip_studio import mount_anip_studio

mount_anip_studio(app, service)
# → Open http://localhost:9100/studio/
```

## Full Studio Product (Docker Compose)

```bash
cd studio
docker compose up --build

# Open http://localhost:8080/design
# API is available at http://localhost:8100
```

To run a published release image instead of tagging local builds as `local`, set
`ANIP_IMAGE_TAG` before starting Compose:

```bash
ANIP_IMAGE_TAG=0.9.0 docker compose up
```

To force a fresh pull of the published release images:

```bash
ANIP_IMAGE_TAG=0.9.0 docker compose pull
ANIP_IMAGE_TAG=0.9.0 docker compose up
```

Useful environment switches:

```bash
# Restore canonical published showcase snapshots into one editable workspace.
STUDIO_SEED_SHOWCASES=1 docker compose up --build

# Host a read-only Studio demo. Unsafe HTTP methods are blocked at the API
# boundary; only GET, HEAD, and OPTIONS remain available.
ANIP_IMAGE_TAG=0.9.0 STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up

# Optionally switch to a read-only database role after startup migrations,
# vocabulary load, and showcase seeding complete.
ANIP_IMAGE_TAG=0.9.0 \
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

## Desktop API Preview

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

This is an API preview for local desktop storage. The future desktop shell is a
separate layer and is not started by this script.

## Views

| View | What It Shows |
|------|---------------|
| Discovery | Protocol version, capabilities, trust posture, endpoints |
| Manifest | Full capability declarations with side effects, costs, scopes |
| JWKS | Public signing keys |
| Audit | Browsable audit entries with filtering (requires bearer token) |
| Checkpoints | Merkle checkpoint list with detail inspection |
| Invoke | Form-based capability invocation with permissions and structured failure display |

## Development

```bash
cd studio
npm install
npm run dev    # Dev server at http://localhost:5173/studio/design
npm run build  # Production build to dist/
npm test       # Run vitest suite
bash sync.sh   # Build for embedded mode and sync to Python package
```

## Studio Assistant Providers

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

## Registry Trust Policy

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
- **Embedded:** Python adapter (`anip-studio`) serves assets at `/studio` with `config.json` marking `embedded: true`
- **Full product:** nginx serves assets at `/` with Design routes under `/design` and same-origin API proxying to `studio-api`
- Full-product `config.json` marks `embedded: false` because the Studio web origin is not itself an ANIP service root; Invoke & Inspect requires an explicit ANIP service URL or `?connect=<service-url>`

## CORS Requirement

When running Studio standalone (at a different origin than the ANIP service), the service must allow cross-origin requests. Add CORS middleware to your service:

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

This is not needed in embedded mode since Studio and the service share the same origin.
