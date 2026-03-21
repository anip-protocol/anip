# Release & Publishing Design

**Goal:** Make ANIP packages publishable to npm and PyPI with a disciplined release workflow, so the ecosystem has a credible delivery model before new language work begins.

**Architecture:** Lockstep versioning across all packages (aligned with protocol version). Manual `workflow_dispatch` trigger, automated validation → build → check → publish → tag/release pipeline. npm for TypeScript (`@anip` scope), PyPI for Python (`anip-*` names).

---

## Scope

**In scope:**
- Version bump from `0.8.0` → `0.11.0` (align with protocol version)
- Package metadata for npm and PyPI publishing
- Per-package READMEs
- Release workflow: validate → build/check → publish → tag/release
- Idempotency documentation for partial failure reruns

**Not in scope:**
- Changelog automation (can add later)
- Automated version bumping tools (changesets, semantic-release)
- Trusted Publishers migration for PyPI
- Publishing examples or conformance suite

## Version Bump

All published packages move from `0.8.0` to `0.11.0` to align with the protocol version (`anip/0.11`).

### TypeScript (13 packages)

Update `version` in each `package.json` and all internal workspace dependency references:

| Package | Location |
|---------|----------|
| `@anip/core` | `packages/typescript/core/` |
| `@anip/crypto` | `packages/typescript/crypto/` |
| `@anip/server` | `packages/typescript/server/` |
| `@anip/service` | `packages/typescript/service/` |
| `@anip/hono` | `packages/typescript/hono/` |
| `@anip/express` | `packages/typescript/express/` |
| `@anip/fastify` | `packages/typescript/fastify/` |
| `@anip/mcp` | `packages/typescript/mcp/` |
| `@anip/mcp-hono` | `packages/typescript/mcp-hono/` |
| `@anip/mcp-express` | `packages/typescript/mcp-express/` |
| `@anip/mcp-fastify` | `packages/typescript/mcp-fastify/` |
| `@anip/rest` | `packages/typescript/rest/` |
| `@anip/graphql` | `packages/typescript/graphql/` |

Example: `"@anip/service": "0.8.0"` → `"@anip/service": "0.11.0"` in both `dependencies` and `devDependencies`.

### Python (8 packages)

Update `version` in each `pyproject.toml` and internal dependency floor versions:

| Package | Location |
|---------|----------|
| `anip-core` | `packages/python/anip-core/` |
| `anip-crypto` | `packages/python/anip-crypto/` |
| `anip-server` | `packages/python/anip-server/` |
| `anip-service` | `packages/python/anip-service/` |
| `anip-fastapi` | `packages/python/anip-fastapi/` |
| `anip-mcp` | `packages/python/anip-mcp/` |
| `anip-rest` | `packages/python/anip-rest/` |
| `anip-graphql` | `packages/python/anip-graphql/` |

Example: `anip-service>=0.8.0` → `anip-service>=0.11.0`.

### Not bumped

- `anip-ts` example: bumped to `0.11.0` (uses `file:` refs, not published)
- `anip-flight-demo` Python example: stays at `0.1.0` (not published)
- `anip-conformance`: stays at `0.1.0` (independent versioning)

### Validation

The release workflow must validate that **all 21 packages** and **all internal dependency references** match the release version. A partial bump must fail validation.

## Package Metadata

### TypeScript — add to each package.json

```json
{
  "license": "Apache-2.0",
  "repository": {
    "type": "git",
    "url": "https://github.com/anip-protocol/anip.git",
    "directory": "packages/typescript/{package-dir}"
  },
  "publishConfig": {
    "access": "public"
  },
  "files": ["dist", "README.md"]
}
```

`"access": "public"` is required — scoped npm packages default to restricted.

`"files"` must be verified per package against actual build output. If a package needs additional artifacts (e.g., type declarations outside `dist/`), the list should be adjusted. The implementer should run `npm pack --dry-run` on each package and verify the contents.

### Python — add to each pyproject.toml

```toml
authors = [{ name = "ANIP Protocol", email = "team@anip.dev" }]
license = { text = "Apache-2.0" }
keywords = ["anip", "agent", "protocol"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

[project.urls]
Repository = "https://github.com/anip-protocol/anip"
```

### Per-Package READMEs

Every published package needs a README that renders on npm/PyPI. Options:

- **Preferred:** each package gets a short `README.md` with package description, install command, and link to the main repo docs.
- **Fallback:** if a package has no README, npm shows `package.json` description only. PyPI shows nothing.

The implementer should create a minimal README for any package that doesn't have one.

## Release Workflow

### Trigger

Manual `workflow_dispatch` with version input (e.g., `0.11.0`). Same as today.

### Pipeline Order

```
1. Validate
   - All 21 package versions match input
   - All internal dependency references match
   - CI checks passed

2. Build + Check (dry run)
   TypeScript:
   - npm ci
   - npm run build --workspaces
   - npm pack each package (verify contents, catch metadata issues)

   Python:
   - For each package in dependency order:
     - rm -rf dist/
     - python -m build
     - twine check dist/*

3. Publish (topological order, stop on failure)
   TypeScript (explicit order):
   1. @anip/core
   2. @anip/crypto
   3. @anip/server
   4. @anip/service
   5. @anip/hono, @anip/express, @anip/fastify
   6. @anip/mcp
   7. @anip/mcp-hono, @anip/mcp-express, @anip/mcp-fastify
   8. @anip/rest, @anip/graphql

   Python (explicit order):
   1. anip-core
   2. anip-crypto
   3. anip-server
   4. anip-service
   5. anip-fastapi
   6. anip-mcp, anip-rest, anip-graphql

4. Tag + Release (only after all publishes succeed)
   - git tag v{version}
   - GitHub Release with auto-generated notes
```

### Failure Handling

If any publish step fails, the workflow stops. No git tag, no GitHub Release. The human investigates and re-runs.

**Idempotency on rerun:** npm and PyPI both reject republishing the same version. After a partial failure:
- Already-published packages cannot be republished at the same version
- The rerun path requires either: (a) skipping already-published packages, or (b) bumping to a patch version (e.g., `0.11.1`)
- The workflow should detect "already exists" errors and skip gracefully rather than failing the entire run

### Required Secrets

| Secret | Purpose |
|--------|---------|
| `NPM_TOKEN` | npm publish token for `@anip` org |
| `PYPI_TOKEN` | PyPI API token (account-scoped) |

### Manual Prerequisites (human, before first release)

1. Create `@anip` organization on [npmjs.com](https://www.npmjs.com)
2. Generate npm automation token, add as `NPM_TOKEN` repo secret
3. Register an account on [pypi.org](https://pypi.org) (if needed)
4. Generate PyPI API token, add as `PYPI_TOKEN` repo secret
5. Verify `anip-*` package names are available on PyPI

## What This Does NOT Cover

- Changelog automation or conventional commits enforcement
- Automated version bump tooling (changesets, semantic-release)
- Trusted Publishers migration for PyPI
- Publishing examples, conformance suite, or agent demos
- Pre-release / alpha / beta versioning policy
