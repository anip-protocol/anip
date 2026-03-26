# ANIP Studio

An inspection and invocation UI for ANIP services. Runs in two modes:

- **Embedded** — mounted at `/studio` inside an ANIP service via the Python `anip-studio` adapter
- **Standalone** — served from a Docker container, connects to any ANIP service via URL

## Embedded Mode

```python
# In your ANIP FastAPI app:
from anip_studio import mount_anip_studio

mount_anip_studio(app, service)
# → Open http://localhost:9100/studio/
```

## Standalone Mode (Docker)

```bash
# Build the image
docker build -t anip-studio studio/

# Run locally
docker run -p 3000:80 anip-studio

# Open http://localhost:3000
# Enter your ANIP service URL in the connect bar
```

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
npm run dev    # Dev server at http://localhost:5173/studio/
npm run build  # Production build to dist/
npm test       # Run vitest suite
bash sync.sh   # Build for embedded mode and sync to Python package
```

## Build Configuration

The base path is controlled by the `VITE_BASE_PATH` environment variable:

| Target | Value | Command |
|--------|-------|---------|
| Embedded | `/studio/` | `bash sync.sh` (sets it automatically) |
| Standalone | `/` | `VITE_BASE_PATH=/ npx vite build` |
| Dev server | `/studio/` | `npm run dev` (uses default) |

## Architecture

- Vue 3 + Vite + TypeScript frontend
- Builds to static assets (no runtime Node dependency)
- **Embedded:** Python adapter (`anip-studio`) serves assets at `/studio` with `config.json` marking `embedded: true`
- **Standalone:** nginx serves assets at `/` with `config.json` marking `embedded: false`
- Connect bar in header for manual URL entry (standalone) or auto-connect (embedded)

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
