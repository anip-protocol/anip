# registryapi

Minimal Go backend scaffold for the ANIP Registry trusted core.

Current scope:

- `GET /registry-api/v1/healthz`
- `GET /registry-api/v1/publications`
- `GET /registry-api/v1/keys`
- `POST /registry-api/v1/publications`
- `GET /registry-api/v1/packages/{packageId}/{version}`
- `GET /registry-api/v1/packages/{packageId}/{version}/download`
- `GET /registry-api/v1/packages/{packageId}/{version}/receipt`

The registry now uses its own Postgres database and runs dedicated migrations from `migrations/*.sql` on startup.

The first publish flow is now implemented.

To publish an existing portable package bundle to a Registry:

```bash
export ANIP_REGISTRY_PUBLISH_TOKEN=...

go run ./cmd/anip package publish-bundle \
  --package-bundle ./path/to/package.anip-package.json \
  --registry-url https://registry.example.com/registry-api/v1
```

Without `--registry-url`, `publish-bundle` writes the exact `PublishPackageRequest`
JSON for review or offline workflows.

The registry computes:

- manifest digest
- Service Definition digest
- recommended lock digest
- normalized README/source-link package metadata
- authenticated publisher identity
- Ed25519-signed receipt metadata
- package download counts as registry operational metadata

on the server side before persisting the immutable package/version record.

`GET /packages/{packageId}/{version}` is an inspection endpoint and does not change counters.
`GET /packages/{packageId}/{version}/download` returns the same package record as an attachment and increments `download_count`; generator clients use this endpoint when resolving trusted registry packages.

Published packages may include:

- `readme`: short Markdown/plain-text package description, limited to 64 KiB.
- `source_links`: up to 8 HTTP(S) project/source/documentation links.

The Registry normalizes these into the manifest before digest/signing, so consumers can inspect trusted package context without treating it as executable behavior. Publish requests are capped at 5 MiB.

Registry publish validation also applies finer-grained package abuse controls:

- manifest, Service Definition, and recommended lock files have separate size ceilings
- package JSON nesting depth is bounded
- packages with excessive capability counts are rejected
- oversized examples and optional attachment-like payloads are rejected
- suspicious binary payloads and raw binary values are rejected
- Service Definition identifiers, path templates, backend operation names, and input metadata are validated before publication

Custom code bundles are not accepted as signed behavior contract material. They may be added later as explicitly typed implementation material through immutable refs with digest pinning. `anip package attach-implementation` can prepare or publish a new package revision whose signed manifest records those refs and optional normalized local bundle tree digests.

## Signing

Registry receipts are signed as `ed25519:<key_id>:<base64_signature>`.

Set `ANIP_REGISTRY_MODE` explicitly:

- `ANIP_REGISTRY_MODE=dev` allows the deterministic local development signing key.
- `ANIP_REGISTRY_MODE=production` refuses to start unless `ANIP_REGISTRY_KEY_ID` and `ANIP_REGISTRY_ED25519_PRIVATE_KEY` are configured.

If `ANIP_REGISTRY_MODE` is omitted, the command defaults to `dev` for local compatibility.

Development mode uses a deterministic local key so tests and local demos work without secret setup. For production deployments, provide a base64-encoded Ed25519 seed or private key:

Generate a keypair:

```bash
cd packages/go
go run ./cmd/anip-registry-keygen --key-id registry-prod-2026-04
```

The command emits shell-ready values for `ANIP_REGISTRY_KEY_ID` and `ANIP_REGISTRY_ED25519_PRIVATE_KEY`.

```bash
ANIP_REGISTRY_DATABASE_URL=postgres://localhost:5432/anip_registry?sslmode=disable \
ANIP_REGISTRY_MODE=production \
ANIP_REGISTRY_KEY_ID=registry-prod-2026-04 \
ANIP_REGISTRY_ED25519_PRIVATE_KEY=<base64-seed-or-private-key> \
go run ./cmd/anip-registry
```

`GET /registry-api/v1/healthz` exposes `signing_mode` and `active_key_id`.
`GET /registry-api/v1/keys` exposes the same signing posture plus public keys for verifier clients.

For key rotation, keep the new private key as the active signer and expose previous public keys with:

```bash
ANIP_REGISTRY_EXTRA_PUBLIC_KEYS=old-key-id=<base64-public-key>,older-key-id=<base64-public-key>
```

Old private keys do not need to remain online for verification.

## Publish Authorization

Read APIs are public. Publication writes should use scoped publisher tokens. During the transition to the public multi-publisher registry, the legacy deployment-wide publish token can be enabled explicitly:

```bash
ANIP_REGISTRY_PUBLISH_TOKEN=<strong-token>
ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED=true
```

Optional publisher identity labels are stamped into publication, package, and receipt records and are included in the signed receipt payload:

```bash
ANIP_REGISTRY_PUBLISHER_ID=studio-local
ANIP_REGISTRY_PUBLISHER_TYPE=studio
```

If scoped token validation fails, or if `ANIP_REGISTRY_PUBLISH_TOKEN` is set without `ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED=true`, `POST /registry-api/v1/publications` returns `401`.

## Official ANIP Publisher Bootstrap

For the public registry, existing pre-public package and template rows can be associated with the official `anip` publisher without rewriting package payloads, template payloads, receipts, or digests:

```bash
ANIP_REGISTRY_BOOTSTRAP_OFFICIAL_ANIP_PUBLISHER=true
ANIP_REGISTRY_OFFICIAL_ANIP_LEGACY_PUBLISHER_IDS=anip,studio-local,studio-dev,local-registry,local-dev-registry,local-dev
```

The bootstrap is idempotent. It creates the official `anip` publisher and namespace, then backfills exact artifact ownership rows for matching legacy publisher IDs. Registry pages display that ownership as the public trust identity while preserving the original signed publication metadata.

## Publisher Self-Service API

Scoped publisher tokens can inspect publisher state and manage additional publish tokens for the same publisher. Token management requires the `manage:tokens` operation in the caller token scopes.

```bash
curl -H "Authorization: Bearer $ANIP_REGISTRY_TOKEN" \
  https://registry.anip.dev/registry-api/v1/me/publisher

curl -H "Authorization: Bearer $ANIP_REGISTRY_TOKEN" \
  https://registry.anip.dev/registry-api/v1/me/artifacts

curl -H "Authorization: Bearer $ANIP_REGISTRY_TOKEN" \
  https://registry.anip.dev/registry-api/v1/me/tokens
```

Create a scoped token:

```bash
curl -X POST \
  -H "Authorization: Bearer $ANIP_REGISTRY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "release bot",
    "scopes": {
      "operations": ["publish:package"],
      "namespaces": ["anip"]
    }
  }' \
  https://registry.anip.dev/registry-api/v1/me/tokens
```

The response returns `bearer_token` once. Registry stores only the token hash and never returns token secrets in list responses. Revoke a token with:

```bash
curl -X DELETE \
  -H "Authorization: Bearer $ANIP_REGISTRY_TOKEN" \
  https://registry.anip.dev/registry-api/v1/me/tokens/<token-id>
```

## Run

```bash
cd packages/go
ANIP_REGISTRY_DATABASE_URL=postgres://localhost:5432/anip_registry?sslmode=disable \
ANIP_REGISTRY_PUBLISH_TOKEN=<strong-token> \
ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED=true \
go run ./cmd/anip-registry
```

Default address:

- `:8200`

Override with:

```bash
ANIP_REGISTRY_DATABASE_URL=postgres://localhost:5432/anip_registry?sslmode=disable \
ANIP_REGISTRY_ADDR=:8300 \
go run ./cmd/anip-registry
```

To seed the demo package after startup:

```bash
ANIP_REGISTRY_DATABASE_URL=postgres://localhost:5432/anip_registry?sslmode=disable \
ANIP_REGISTRY_SEED_DEMO=1 \
go run ./cmd/anip-registry
```

## UI

The Registry UI can be served by the Go Registry backend at `/registry` when a built UI directory is available.

```bash
cd registry
VITE_BASE_PATH=/registry/ npm run build

cd ../packages/go
ANIP_REGISTRY_DATABASE_URL=postgres://localhost:5432/anip_registry?sslmode=disable \
ANIP_REGISTRY_UI_DIR=../../registry/dist \
go run ./cmd/anip-registry
```

If `ANIP_REGISTRY_UI_DIR` is not set, the command attempts to discover `registry/dist` for local development.

## Trust-loop smoke

Run the end-to-end Registry trust-loop smoke against a live Registry:

```bash
cd packages/go
go run ./cmd/anip-registry-smoke \
  --registry-url http://127.0.0.1:8200
```

The smoke publishes a fresh Studio-shaped package, confirms `/registry` is served, verifies the signed Registry receipt, and generates a TypeScript project from the exact Registry package identity.

To also prove Studio can persist the remote publication artifact:

```bash
cd packages/go
go run ./cmd/anip-registry-smoke \
  --registry-url http://127.0.0.1:8200 \
  --studio-api-url http://127.0.0.1:8100
```
