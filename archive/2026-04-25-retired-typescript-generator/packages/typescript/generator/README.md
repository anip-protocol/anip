# @anip-dev/generator-typescript

Standalone ANIP generator and TypeScript build pack.

This package consumes an exported `anip-service-definition.json` and emits a runnable TypeScript ANIP service project that uses the generic `@anip-dev/service` and `@anip-dev/hono` runtime packages.

## Scope of the first slice

The generated project includes:

- HTTP server bootstrap
- discovery, manifest, JWKS, token, permissions, and invoke endpoints
- generated capability declarations and invoke routing
- generic policy seam
- generic backend adapter seam
- generated smoke tests

The generated project is runnable as-is, but provider-specific backend execution remains an explicit extension seam in `src/runtime/backend-adapter.ts` and `src/runtime/policy.ts`.

## CLI

```bash
anip-generate-typescript \
  --definition ./anip-service-definition.json \
  --output ./generated/my-service
```
