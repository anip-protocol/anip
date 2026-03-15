# CI & Versioning Design

## Goal

Establish reliable CI gates and a clear versioning policy for the ANIP package ecosystem before adding more bindings or publishing to registries.

## Decisions

- **Two workflow files**: `ci-python.yml` and `ci-typescript.yml`
- **Triggers**: push to `main` + PRs targeting `main`
- **Path filters**: each workflow scoped to its language's packages, examples, and own workflow file
- **Approach**: build-chain with smart ordering (Approach A) — install and test everything sequentially in one job per matrix entry
- **CI gates only** — no publish automation yet
- **Lockstep versioning** at `0.3.x` across all 10 core packages

## Workflow Structure

### Triggers (both workflows)

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

With path filters scoping each workflow to its language directory, example directory, and own workflow file.

### ci-python.yml

**Matrix**: `python-version: [3.11, 3.12]`

Steps:
1. Checkout
2. Set up Python (matrix version)
3. Upgrade pip
4. Install packages in dependency order with dev extras:
   - `anip-core[dev]` → `anip-crypto[dev]` → `anip-server[dev]` → `anip-service[dev]` → `anip-fastapi[dev]`
5. Compile check: `python -m compileall packages/python/ examples/anip/`
6. Run tests per package:
   - `pytest packages/python/anip-core/tests/`
   - `pytest packages/python/anip-crypto/tests/`
   - `pytest packages/python/anip-server/tests/`
   - `pytest packages/python/anip-service/tests/`
   - `pytest packages/python/anip-fastapi/tests/`
7. Example smoke test:
   - `pip install -e ./examples/anip`
   - `pytest examples/anip/tests/` (if tests exist)

### ci-typescript.yml

**Matrix**: `node-version: [20, 22]`

Steps:
1. Checkout
2. Set up Node (matrix version)
3. Install workspace dependencies: `cd packages/typescript && npm ci`
4. Build all packages in dependency order (tsc doubles as type-check):
   - `npx tsc -p core/tsconfig.json`
   - `npx tsc -p crypto/tsconfig.json`
   - `npx tsc -p server/tsconfig.json`
   - `npx tsc -p service/tsconfig.json`
   - `npx tsc -p hono/tsconfig.json`
5. Run tests per package:
   - `npm test --workspace=@anip/core`
   - `npm test --workspace=@anip/crypto`
   - `npm test --workspace=@anip/server`
   - `npm test --workspace=@anip/service`
   - `npm test --workspace=@anip/hono`
6. Example smoke test:
   - `cd examples/anip-ts && npm ci && npm test`

## Versioning Policy

- **Lockstep versioning**: all 10 core packages (5 Python + 5 TypeScript) share the same version
- **Current version**: `0.3.0`
- **Semver progression**: `0.3.x` for bugfixes, `0.4.0` for next protocol line
- **Prerelease tags**: `0.3.1-dev.1`, `0.3.1-beta.1` for in-progress builds
- **Build metadata**: git SHA and CI artifacts, not baked into version numbers
- **Adapters** (`0.1.0`): version independently, out of scope
- **Protocol version**: packages declare support for ANIP protocol 0.3, separate from package version

## Package Metadata Updates

- Add `"engines": { "node": ">=20" }` to all TypeScript `package.json` files
- Add `python_requires = ">=3.11"` to all Python `pyproject.toml` files (if not already present)

## Explicitly Not In Scope

- Lint / formatting checks
- Publish automation (PyPI, npm)
- Version alignment enforcement in CI
- Coverage reporting
- Adapter CI
- Docs/spec sanity checks
