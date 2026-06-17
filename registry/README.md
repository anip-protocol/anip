# ANIP Registry UI

Thin web UI for the ANIP Registry service.

This app is intentionally non-authoritative. The Go registry backend is the trusted core.

## Development

```bash
npm install
npm run dev
```

By default the UI expects the registry backend at `http://127.0.0.1:8200`.

Override with:

```bash
VITE_REGISTRY_BACKEND_URL=http://127.0.0.1:8200 npm run dev
```

To serve the built UI from the Go Registry backend at `/registry`:

```bash
cd registry
npm run build

cd ../packages/go
ANIP_REGISTRY_DATABASE_URL=postgres://localhost:5432/anip_registry?sslmode=disable \
ANIP_REGISTRY_PUBLISH_TOKEN=<strong-token> \
ANIP_REGISTRY_UI_DIR=../../registry/dist \
go run ./cmd/anip-registry
```

Then open `http://127.0.0.1:8200/registry`.

`VITE_BASE_PATH` defaults to `/registry/` so normal builds match the Go Registry mount point. Override it only when intentionally serving the UI from another path.

The receipt panel displays the Registry signature algorithm and key id returned by the trusted Go backend. The browser UI does not validate signatures; verifier clients should use the verifier, which resolves `GET /registry-api/v1/keys`.

The `/publisher` page provides token-based publisher self-service for registries backed by Postgres. Paste a scoped publisher token to inspect publisher identity, owned artifacts, and publish tokens. Token creation and revocation require the `manage:tokens` operation in the connected token.

## Local Docker Compose

Run a clean local Registry with Postgres and the built Registry UI:

```bash
cd registry
docker compose up --build
```

Open `http://127.0.0.1:8200/registry`.

For a clean reset, stop the stack and remove the Registry database volume:

```bash
docker compose down -v --remove-orphans
```

To run the full local Registry trust-loop smoke with a clean database, built
image, package publication, UI route checks, verifier check, and generator check:

```bash
registry/scripts/smoke-compose.sh
```

The smoke stack removes its Compose volume before each run and tears itself down
afterward. Set `ANIP_REGISTRY_SMOKE_KEEP_STACK=1` to leave it running for manual
inspection. Set `ANIP_REGISTRY_SMOKE_SKIP_BUILD=1` to reuse an existing local
`anipprotocol/registry:local` image during repeat smoke runs.

To run a published release image instead of tagging the build as `local`, set
`ANIP_IMAGE_TAG`:

```bash
ANIP_IMAGE_TAG=0.24.5 docker compose up
```

The compose stack defaults to development signing mode and a local publish token:

```bash
ANIP_REGISTRY_PUBLISH_TOKEN=local-dev-registry-token
ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED=true
```

Override ports or seed demo data with:

```bash
ANIP_REGISTRY_PORT=8300 \
ANIP_REGISTRY_SEED_DEMO=1 \
docker compose up --build
```

For production-like local testing, provide a real signing key:

```bash
ANIP_REGISTRY_MODE=production \
ANIP_REGISTRY_KEY_ID=<key-id> \
ANIP_REGISTRY_ED25519_PRIVATE_KEY=<base64-seed-or-private-key> \
docker compose up --build
```
