# Release & Publishing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump all packages to 0.11.0, add npm/PyPI metadata, and update the release workflow to validate → build/check → publish → tag/release.

**Architecture:** Lockstep version bump across 21 packages. Add publishing metadata to all package.json and pyproject.toml files. Create per-package READMEs. Rewrite release.yml with topological publish order and pre-publish checks.

**Tech Stack:** npm (scoped @anip), PyPI (anip-*), GitHub Actions

**Design doc:** `docs/plans/2026-03-20-release-publishing-design.md`

---

## Task 1: Version Bump (0.8.0 → 0.11.0)

**Files to modify:**

All 13 TypeScript package.json files + root workspace package-lock.json:
- `packages/typescript/core/package.json`
- `packages/typescript/crypto/package.json`
- `packages/typescript/server/package.json`
- `packages/typescript/service/package.json`
- `packages/typescript/hono/package.json`
- `packages/typescript/express/package.json`
- `packages/typescript/fastify/package.json`
- `packages/typescript/mcp/package.json`
- `packages/typescript/mcp-hono/package.json`
- `packages/typescript/mcp-express/package.json`
- `packages/typescript/mcp-fastify/package.json`
- `packages/typescript/rest/package.json`
- `packages/typescript/graphql/package.json`

All 8 Python pyproject.toml files:
- `packages/python/anip-core/pyproject.toml`
- `packages/python/anip-crypto/pyproject.toml`
- `packages/python/anip-server/pyproject.toml`
- `packages/python/anip-service/pyproject.toml`
- `packages/python/anip-fastapi/pyproject.toml`
- `packages/python/anip-mcp/pyproject.toml`
- `packages/python/anip-rest/pyproject.toml`
- `packages/python/anip-graphql/pyproject.toml`

Example app:
- `examples/anip-ts/package.json`

- [ ] **Step 1: Bump TypeScript package versions**

In every TypeScript package.json, change `"version": "0.8.0"` to `"version": "0.11.0"`.

Also update every `@anip/*` dependency reference from `"0.8.0"` to `"0.11.0"` in both `dependencies` and `devDependencies`. The exact references to change:

| Package | dependencies @anip/* | devDependencies @anip/* |
|---------|---------------------|------------------------|
| core | — | — |
| crypto | core | — |
| server | core, crypto | — |
| service | core, crypto, server | — |
| hono | service | — |
| express | service | — |
| fastify | service | — |
| mcp | service | core, server |
| mcp-hono | mcp, service | core, server, hono |
| mcp-express | mcp, service | core, server, express |
| mcp-fastify | mcp, service | core, server, fastify |
| rest | service | core, server, hono |
| graphql | service | core, hono, server |

- [ ] **Step 2: Bump Python package versions**

In every Python pyproject.toml, change `version = "0.8.0"` to `version = "0.11.0"`.

Also change internal anip-* dependencies from `>=0.8.0` to `==0.11.0`:

| Package | Internal deps to change |
|---------|------------------------|
| anip-core | — |
| anip-crypto | `anip-core>=0.8.0` → `anip-core==0.11.0` |
| anip-server | `anip-core>=0.8.0` → `anip-core==0.11.0`, `anip-crypto>=0.8.0` → `anip-crypto==0.11.0` |
| anip-service | `anip-core>=0.8.0` → `anip-core==0.11.0`, `anip-crypto>=0.8.0` → `anip-crypto==0.11.0`, `anip-server>=0.8.0` → `anip-server==0.11.0` |
| anip-fastapi | `anip-service>=0.8.0` → `anip-service==0.11.0` |
| anip-mcp | `anip-service>=0.8.0` → `anip-service==0.11.0` |
| anip-rest | `anip-service>=0.8.0` → `anip-service==0.11.0`, `anip-fastapi>=0.8.0` → `anip-fastapi==0.11.0` |
| anip-graphql | `anip-service>=0.8.0` → `anip-service==0.11.0` |

**Important:** Only change `anip-*` internal deps to `==`. External deps like `fastapi>=0.115.0`, `mcp>=1.0.0`, `pydantic>=2.0.0` keep their floor bounds.

- [ ] **Step 3: Bump example app version**

In `examples/anip-ts/package.json`, change `"version": "0.8.0"` to `"version": "0.11.0"`. (Uses `file:` refs, not version-pinned deps.)

- [ ] **Step 4: Regenerate package-lock.json**

```bash
cd packages/typescript && npm install
```

This updates the lockfile to reflect the new versions.

- [ ] **Step 5: Verify all tests pass**

```bash
cd packages/typescript && npm run build --workspaces && npm test --workspaces
```

For Python, reinstall all 8 packages and test (use an existing venv or the example app's venv):
```bash
pip install -e "packages/python/anip-core" -e "packages/python/anip-crypto" -e "packages/python/anip-server" -e "packages/python/anip-service" -e "packages/python/anip-fastapi" -e "packages/python/anip-mcp" -e "packages/python/anip-rest" -e "packages/python/anip-graphql"
pytest packages/python/anip-core/tests/ packages/python/anip-crypto/tests/ packages/python/anip-server/tests/ packages/python/anip-service/tests/ packages/python/anip-fastapi/tests/ packages/python/anip-mcp/tests/ packages/python/anip-rest/tests/ packages/python/anip-graphql/tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/ examples/anip-ts/package.json
git commit -m "chore: bump all packages from 0.8.0 to 0.11.0

Align package versions with protocol version (anip/0.11).
Python internal deps use exact pins (==) for lockstep."
```

---

## Task 2: Package Metadata + READMEs

**Files to modify:** Same 13 TS package.json + 8 PY pyproject.toml files.
**Files to create:** 21 per-package README.md files.

- [ ] **Step 1: Add metadata to TypeScript package.json files**

Add these fields to each of the 13 TypeScript package.json files:

```json
{
  "license": "Apache-2.0",
  "repository": {
    "type": "git",
    "url": "https://github.com/anip-protocol/anip.git",
    "directory": "packages/typescript/{dir-name}"
  },
  "publishConfig": {
    "access": "public"
  },
  "files": ["dist", "README.md"]
}
```

Replace `{dir-name}` with the actual directory name (e.g., `core`, `crypto`, `mcp-hono`).

After adding, verify the `files` list per package:
```bash
cd packages/typescript/{pkg} && npm pack --dry-run
```
Confirm `dist/` contains all `.js` and `.d.ts` files. If any package needs additional files, adjust.

- [ ] **Step 2: Add metadata to Python pyproject.toml files**

Add these fields to each of the 8 Python pyproject.toml files:

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

- [ ] **Step 3: Create per-package README.md files**

Create a minimal README.md in each of the 21 package directories. Template:

```markdown
# {package-name}

{description from package.json or pyproject.toml}

Part of the [ANIP](https://github.com/anip-protocol/anip) protocol ecosystem.

## Install

\`\`\`bash
npm install {package-name}
\`\`\`

or for Python:

\`\`\`bash
pip install {package-name}
\`\`\`

## Documentation

See the [ANIP repository](https://github.com/anip-protocol/anip) for full documentation.
```

Adjust install command per language. Include the package description from the existing `description` field.

- [ ] **Step 4: Commit**

```bash
git add packages/
git commit -m "chore: add npm/PyPI metadata and per-package READMEs"
```

---

## Task 3: Release Workflow Update

**Files:**
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Rewrite release.yml**

Read the current workflow at `.github/workflows/release.yml` first. Then rewrite with this structure:

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Release version (e.g., 0.11.0)"
        required: true
      prerelease:
        description: "Mark as prerelease"
        type: boolean
        default: false

jobs:
  validate:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # full history + tags for tag-exists check

      - name: Validate running from main
        run: |
          if [ "${{ github.ref }}" != "refs/heads/main" ]; then
            echo "Releases must run from the main branch"
            exit 1
          fi

      - name: Validate required CI checks passed
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: |
          SHA=$(git rev-parse HEAD)
          REQUIRED_CHECKS=("test (3.11)" "test (3.12)" "test (20)" "test (22)")
          ERRORS=0
          for CHECK in "${REQUIRED_CHECKS[@]}"; do
            STATUS=$(gh api "repos/$GH_REPO/commits/$SHA/check-runs" \
              --jq ".check_runs[] | select(.name == \"$CHECK\") | .conclusion" \
              | head -1)
            if [ "$STATUS" = "success" ]; then
              echo "OK: $CHECK = success"
            else
              echo "FAIL: $CHECK status is '${STATUS:-not found}' (expected 'success')"
              ERRORS=$((ERRORS + 1))
            fi
          done
          if [ "$ERRORS" -gt 0 ]; then exit 1; fi

      - name: Validate tag does not exist
        run: |
          TAG="v${{ github.event.inputs.version }}"
          if git rev-parse "$TAG" >/dev/null 2>&1; then
            echo "FAIL: Tag '$TAG' already exists"
            exit 1
          fi
          echo "OK: Tag '$TAG' is available"

      - name: Validate version format
        run: |
          if ! echo "${{ github.event.inputs.version }}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then
            echo "Invalid version format"
            exit 1
          fi

      - name: Validate TypeScript package versions and internal deps
        working-directory: packages/typescript
        run: |
          VERSION="${{ github.event.inputs.version }}"
          FAILED=0
          for pkg in core crypto server service hono express fastify mcp mcp-hono mcp-express mcp-fastify rest graphql; do
            PKG_VERSION=$(node -p "require('./$pkg/package.json').version")
            if [ "$PKG_VERSION" != "$VERSION" ]; then
              echo "FAIL: $pkg version is $PKG_VERSION, expected $VERSION"
              FAILED=1
            fi
            # Check all @anip/* deps match the release version
            for dep_field in dependencies devDependencies; do
              STALE=$(node -p "
                const deps = require('./$pkg/package.json')['$dep_field'] || {};
                Object.entries(deps)
                  .filter(([k,v]) => k.startsWith('@anip/') && v !== '$VERSION')
                  .map(([k,v]) => k + '=' + v)
                  .join(',')
              ")
              if [ -n "$STALE" ]; then
                echo "FAIL: $pkg $dep_field has stale @anip deps: $STALE"
                FAILED=1
              fi
            done
          done
          if [ "$FAILED" -eq 1 ]; then exit 1; fi
          echo "All 13 TypeScript packages and internal deps at version $VERSION"

      - name: Validate Python package versions and internal deps
        run: |
          VERSION="${{ github.event.inputs.version }}"
          FAILED=0
          for pkg in anip-core anip-crypto anip-server anip-service anip-fastapi anip-mcp anip-rest anip-graphql; do
            PKG_VERSION=$(grep '^version' packages/python/$pkg/pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
            if [ "$PKG_VERSION" != "$VERSION" ]; then
              echo "FAIL: $pkg version is $PKG_VERSION, expected $VERSION"
              FAILED=1
            fi
            # Check internal anip-* deps use exact lockstep pin (==VERSION)
            # Catch both wrong versions AND wrong operators (>= instead of ==)
            INTERNAL_DEPS=$(grep -E '"anip-(core|crypto|server|service|fastapi)' packages/python/$pkg/pyproject.toml || true)
            if [ -n "$INTERNAL_DEPS" ]; then
              # Every internal dep line must contain ==VERSION
              BAD=$(echo "$INTERNAL_DEPS" | grep -v "==$VERSION" || true)
              if [ -n "$BAD" ]; then
                echo "FAIL: $pkg has non-lockstep internal deps:"
                echo "$BAD"
                FAILED=1
              fi
            fi
          done
          if [ "$FAILED" -eq 1 ]; then exit 1; fi
          echo "All 8 Python packages and internal deps at version $VERSION"

  publish-typescript:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          registry-url: "https://registry.npmjs.org"

      - name: Install and build
        working-directory: packages/typescript
        run: |
          npm ci
          npm run build --workspaces

      - name: Dry run — verify packages
        working-directory: packages/typescript
        run: |
          for pkg in core crypto server service hono express fastify mcp mcp-hono mcp-express mcp-fastify rest graphql; do
            echo "=== Checking $pkg ==="
            cd $pkg && npm pack --dry-run && cd ..
          done

      - name: Publish in topological order
        working-directory: packages/typescript
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
        run: |
          set -e
          publish_or_skip() {
            local pkg=$1
            cd $pkg
            OUTPUT=$(npm publish --access public 2>&1) && {
              echo "OK: $pkg published"
              cd ..
              return 0
            }
            # npm publish failed — check if it's "already exists"
            if echo "$OUTPUT" | grep -qi "cannot publish over the previously published"; then
              echo "SKIP: $pkg@$(node -p 'require("./package.json").version') already published"
              cd ..
              return 0
            fi
            echo "FAIL: $pkg publish failed:"
            echo "$OUTPUT"
            cd ..
            return 1
          }

          # Layer 1: no deps
          publish_or_skip core

          # Layer 2: depends on core
          publish_or_skip crypto

          # Layer 3: depends on core, crypto
          publish_or_skip server

          # Layer 4: depends on core, crypto, server
          publish_or_skip service

          # Layer 5: depends on service
          publish_or_skip hono
          publish_or_skip express
          publish_or_skip fastify

          # Layer 6: depends on service
          publish_or_skip mcp

          # Layer 7: depends on mcp + framework
          publish_or_skip mcp-hono
          publish_or_skip mcp-express
          publish_or_skip mcp-fastify

          # Layer 8: depends on service
          publish_or_skip rest
          publish_or_skip graphql

  publish-python:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install build tools
        run: pip install build twine

      - name: Build and check all packages
        run: |
          for pkg in anip-core anip-crypto anip-server anip-service anip-fastapi anip-mcp anip-rest anip-graphql; do
            echo "=== Building $pkg ==="
            cd packages/python/$pkg
            rm -rf dist/
            python -m build
            twine check dist/*
            cd ../../..
          done

      - name: Publish in dependency order
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: |
          set -e
          publish_or_skip() {
            local pkg=$1
            cd packages/python/$pkg
            OUTPUT=$(twine upload dist/* 2>&1) && {
              echo "OK: $pkg published"
              cd ../../..
              return 0
            }
            # twine upload failed — check if it's "already exists"
            if echo "$OUTPUT" | grep -qi "File already exists"; then
              echo "SKIP: $pkg already published on PyPI"
              cd ../../..
              return 0
            fi
            echo "FAIL: $pkg publish failed:"
            echo "$OUTPUT"
            cd ../../..
            return 1
          }

          publish_or_skip anip-core
          publish_or_skip anip-crypto
          publish_or_skip anip-server
          publish_or_skip anip-service
          publish_or_skip anip-fastapi
          publish_or_skip anip-mcp
          publish_or_skip anip-rest
          publish_or_skip anip-graphql

  release:
    needs: [publish-typescript, publish-python]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - name: Create tag
        run: |
          git tag "v${{ github.event.inputs.version }}"
          git push origin "v${{ github.event.inputs.version }}"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: "v${{ github.event.inputs.version }}"
          generate_release_notes: true
          prerelease: ${{ github.event.inputs.prerelease }}
```

**Note:** The `publish_or_skip` function handles idempotency for reruns after partial failure. The exact error detection for "already published" may need adjustment — npm returns exit code 1 with "EPUBLISHCONFLICT", twine outputs "File already exists". The implementer should test the exact error strings and adjust the grep patterns.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "chore: update release workflow for full npm/PyPI publishing

- Validate all 21 packages (was 12)
- Build + dry-run check before publish
- Explicit topological publish order
- Tag/release only after all publishes succeed
- Idempotent reruns for partial failure recovery"
```

---

## Task 4: Verification

- [ ] **Step 1: Run all TypeScript tests**

```bash
cd packages/typescript && npm ci && npm run build --workspaces && npm test --workspaces
```

- [ ] **Step 2: Run all Python tests**

```bash
pytest packages/python/anip-core/tests/ packages/python/anip-crypto/tests/ packages/python/anip-server/tests/ packages/python/anip-service/tests/ packages/python/anip-fastapi/tests/ packages/python/anip-mcp/tests/ packages/python/anip-rest/tests/ packages/python/anip-graphql/tests/ -v
```

- [ ] **Step 3: Run conformance suite against both example apps**

```bash
# Start Python app, run conformance
cd examples/anip && .venv/bin/python -m uvicorn app:app --port 8090 &
sleep 3
cd conformance && .venv/bin/pytest --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key --sample-inputs=samples/flight-service.json -v
```

- [ ] **Step 4: Verify npm pack output for each TS package**

```bash
cd packages/typescript
for pkg in core crypto server service hono express fastify mcp mcp-hono mcp-express mcp-fastify rest graphql; do
  echo "=== $pkg ==="
  cd $pkg && npm pack --dry-run 2>&1 | head -20 && cd ..
done
```

Confirm each package contains `dist/`, `README.md`, `package.json` and no source/test files.

- [ ] **Step 5: Verify Python build for each package**

```bash
for pkg in anip-core anip-crypto anip-server anip-service anip-fastapi anip-mcp anip-rest anip-graphql; do
  echo "=== $pkg ==="
  cd packages/python/$pkg
  rm -rf dist/
  python -m build
  twine check dist/*
  cd ../../..
done
```

- [ ] **Step 6: Commit any fixes**

---

## Manual Prerequisites (human, before first release)

These are **not automated** — the human must do these before triggering the release workflow:

1. Create `@anip` organization on [npmjs.com](https://www.npmjs.com/org/create)
2. Generate npm automation token with publish permissions
3. Add as `NPM_TOKEN` in GitHub repo Settings → Secrets → Actions
4. Register on [pypi.org](https://pypi.org/account/register/) if needed
5. Generate PyPI API token (account scope)
6. Add as `PYPI_TOKEN` in GitHub repo Settings → Secrets → Actions
7. Verify `anip-*` package names are available on PyPI (first publish claims them)
