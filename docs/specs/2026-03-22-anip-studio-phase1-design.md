# ANIP Studio Phase 1 Design — Inspection UI

## Purpose

A web-based inspection UI embedded at `/studio` on any ANIP service. Phase 1 is read-only — it makes ANIP services legible by rendering discovery, manifest, keys, audit, and checkpoints in navigable panels. No invocation, no workflow editing, no token management.

Point Studio at a running ANIP service and immediately see what it declares, what trust posture it exposes, and what evidence it produces.

## Architecture

### Frontend

Vue 3 + Vite single-page application at `studio/` (top-level directory).

```
studio/
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   ├── App.vue                  # Shell: URL bar + sidebar navigation
│   ├── views/
│   │   ├── DiscoveryView.vue    # Discovery document + posture
│   │   ├── ManifestView.vue     # Capabilities, side effects, costs, scopes
│   │   ├── JwksView.vue         # Public keys
│   │   ├── AuditView.vue        # Audit log browser (requires bearer)
│   │   └── CheckpointsView.vue  # Checkpoint list + proof inspection
│   └── components/
│       ├── JsonPanel.vue        # Collapsible JSON tree renderer
│       ├── CapabilityCard.vue   # Single capability with side effect, cost, scope
│       ├── PostureBar.vue       # Trust/disclosure/audit posture summary bar
│       ├── AuditEntry.vue       # Single audit entry row
│       ├── BearerInput.vue      # Token input field for authenticated views
│       └── StatusBadge.vue      # Colored status indicator
├── dist/                        # Built static assets (checked in)
└── README.md
```

Builds to `studio/dist/` — static HTML/CSS/JS with no runtime dependencies.

### Views

**5 views, split by auth requirement:**

| View | Endpoint | Auth | What it shows |
|------|----------|------|---------------|
| Discovery | `GET /.well-known/anip` | None | Protocol version, compliance, capabilities summary, trust level, posture (audit, disclosure, anchoring), endpoints |
| Manifest | `GET /anip/manifest` | None | Full capability declarations — name, description, side effect, cost, minimum scope, prerequisites. Signature header displayed (not verified client-side in Phase 1). |
| JWKS | `GET /.well-known/jwks.json` | None | Public keys — algorithm, curve, key ID. Table format. |
| Audit | `POST /anip/audit` | Bearer token | Browsable audit entries — timestamp, capability, success/failure, event class, retention tier. Filterable by capability, since, limit. |
| Checkpoints | `GET /anip/checkpoints` | None | Checkpoint list — ID, timestamp, merkle root, entry count, range. Detail view for individual checkpoints. |

### App Shell

- **URL bar** at top — pre-filled with current origin when embedded, editable for standalone use
- **Sidebar** — 5 navigation items (Discovery, Manifest, JWKS, Audit, Checkpoints)
- **Main panel** — renders the selected view
- **Bearer input** — appears inline when Audit view is selected. Persists in session storage for the duration of the tab.

### Data Flow

1. User opens `/studio` (or enters a URL in standalone mode)
2. App fetches `GET /.well-known/anip` to confirm it's an ANIP service
3. Sidebar populates. Discovery view renders first.
4. User navigates to other views — each fetches its endpoint on demand
5. Audit view prompts for bearer token before fetching

All fetches go directly to the ANIP service — no proxy, no backend. When embedded (same origin), no CORS. In standalone mode, the target service must allow CORS.

### Bootstrap Config

When embedded, the adapter serves a small `config.json` at `/studio/config.json`:

```json
{
  "base_url": "http://localhost:8000",
  "service_id": "anip-travel-showcase"
}
```

The frontend reads this on load to set the default service URL. If absent (standalone mode), the URL bar starts empty.

## Distribution

### Build

```bash
cd studio && npm install && npm run build
```

Output: `studio/dist/` containing `index.html`, CSS, and JS bundles.

Built assets are checked into the repo. Regenerated when the frontend changes.

### Python Adapter

New Python package: `anip-studio` at `packages/python/anip-studio/`.

```python
from anip_studio import mount_anip_studio

mount_anip_studio(app, service)
```

This mounts:
- `GET /studio` → serves `index.html`
- `GET /studio/{path:path}` → serves static assets from `dist/`
- `GET /studio/config.json` → returns bootstrap config with service URL and ID

The `dist/` files are included as Python package data. No Node runtime needed at serving time.

SPA routing: all `/studio/*` paths that don't match a static file fall back to `index.html`.

### Showcase Integration

Each showcase app adds one line:

```python
from anip_studio import mount_anip_studio
mount_anip_studio(app, service)
```

### Other Runtime Adapters (Later)

Go, Java, C# adapters follow the same pattern — serve the same `dist/` files from their framework's static file serving mechanism. Not in Phase 1.

## UI Design Principles

- **Information density over decoration.** Studio is a developer tool, not a marketing page. Show data, not chrome.
- **JSON is the fallback.** Every view has a "Raw JSON" toggle that shows the raw endpoint response.
- **Copy-friendly.** Token IDs, endpoints, key IDs — all one-click copyable.
- **No dark magic.** Studio only calls documented ANIP protocol endpoints. It does nothing a `curl` command couldn't do.

## What Phase 1 Does NOT Include

- Capability invocation (Phase 2)
- Token issuance or management (Phase 2)
- Streaming visualization (Phase 2)
- Lineage visualization (Phase 2)
- Permissions inspection tied to live authority (Phase 2)
- Client-side manifest signature verification
- Cross-service comparison
- Multi-runtime adapters (Go, Java, C# — later)

## Success Criteria

1. `mount_anip_studio(app, service)` works with zero configuration
2. Opening `/studio` in a browser shows the discovery view immediately
3. All 5 views render correctly against the travel, finance, and DevOps showcase apps
4. Audit view works with a valid bearer token
5. The same `dist/` assets can be served standalone (without embedding) by pointing at any ANIP service URL
