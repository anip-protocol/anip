# ANIP Studio

An embedded inspection UI for ANIP services. Mount it at `/studio` on any ANIP service to get a rich, interactive dashboard for exploring discovery documents, manifests, keys, audit logs, and checkpoints.

## Quick Start

```python
# In your ANIP FastAPI app:
from anip_studio import mount_anip_studio

mount_anip_studio(app, service)
# → Open http://localhost:8000/studio/
```

## Views

| View | What It Shows |
|------|---------------|
| Discovery | Protocol version, capabilities, trust posture, endpoints |
| Manifest | Full capability declarations with side effects, costs, scopes |
| JWKS | Public signing keys |
| Audit | Browsable audit entries with filtering (requires bearer token) |
| Checkpoints | Merkle checkpoint list with detail inspection |

## Development

```bash
cd studio
npm install
npm run dev    # Dev server at http://localhost:5173/studio/
npm run build  # Production build to dist/
bash sync.sh   # Sync dist/ to Python package
```

## Architecture

- Vue 3 + Vite + TypeScript frontend
- Builds to static assets (no runtime Node dependency)
- Python adapter (`anip-studio`) serves assets at `/studio`
- Bootstrap config at `/studio/config.json` tells the SPA it's embedded

## Phase 1 Limitations

- Read-only inspection (no capability invocation)
- Assumes ANIP service is mounted at origin root (no path prefix support)
- Manifest signature displayed but not verified client-side
