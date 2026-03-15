# CI & Versioning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add GitHub Actions CI workflows for Python and TypeScript packages, and add `engines` metadata to TypeScript packages.

**Architecture:** Two workflow files (`ci-python.yml`, `ci-typescript.yml`) each run install → build → test → example smoke test in dependency order. One job per workflow, matrix on language versions. Package metadata updates add `engines.node >= 20` to TypeScript packages.

**Tech Stack:** GitHub Actions, Python 3.11/3.12, Node 20/22, pytest, vitest, tsc

---

### Task 1: Add `engines` field to all TypeScript package.json files

**Files:**
- Modify: `packages/typescript/core/package.json`
- Modify: `packages/typescript/crypto/package.json`
- Modify: `packages/typescript/server/package.json`
- Modify: `packages/typescript/service/package.json`
- Modify: `packages/typescript/hono/package.json`

**Step 1: Add engines field to each package.json**

Add this field at the top level of each `package.json`:

```json
"engines": {
  "node": ">=20"
},
```

Place it after `"type": "module"` (or after `"description"` if no `type` field).

**Step 2: Verify JSON is valid**

Run from `packages/typescript/`:
```bash
for pkg in core crypto server service hono; do node -e "JSON.parse(require('fs').readFileSync('$pkg/package.json','utf8'))" && echo "$pkg OK"; done
```

Expected: all 5 print OK.

**Step 3: Commit**

```bash
git add packages/typescript/*/package.json
git commit -m "chore: add engines.node >= 20 to all TypeScript packages"
```

---

### Task 2: Create Python CI workflow

**Files:**
- Create: `.github/workflows/ci-python.yml`

**Step 1: Create the workflow file**

```yaml
name: CI — Python

on:
  push:
    branches: [main]
    paths:
      - "packages/python/**"
      - "examples/anip/**"
      - ".github/workflows/ci-python.yml"
  pull_request:
    branches: [main]
    paths:
      - "packages/python/**"
      - "examples/anip/**"
      - ".github/workflows/ci-python.yml"

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Upgrade pip
        run: python -m pip install --upgrade pip

      - name: Install packages in dependency order
        run: |
          pip install -e ./packages/python/anip-core[dev]
          pip install -e ./packages/python/anip-crypto[dev]
          pip install -e ./packages/python/anip-server[dev]
          pip install -e ./packages/python/anip-service[dev]
          pip install -e ./packages/python/anip-fastapi[dev]

      - name: Compile check
        run: python -m compileall packages/python/ examples/anip/

      - name: Test anip-core
        run: pytest packages/python/anip-core/tests/ -v

      - name: Test anip-crypto
        run: pytest packages/python/anip-crypto/tests/ -v

      - name: Test anip-server
        run: pytest packages/python/anip-server/tests/ -v

      - name: Test anip-service
        run: pytest packages/python/anip-service/tests/ -v

      - name: Test anip-fastapi
        run: pytest packages/python/anip-fastapi/tests/ -v

      - name: Install and test Python example
        run: |
          pip install -e ./examples/anip[dev]
          pytest examples/anip/tests/ -v
```

**Step 2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci-python.yml'))"
```

Expected: no error (requires PyYAML installed, or use `node -e "..."` with js-yaml).

**Step 3: Commit**

```bash
git add .github/workflows/ci-python.yml
git commit -m "ci: add Python CI workflow (3.11, 3.12)"
```

---

### Task 3: Create TypeScript CI workflow

**Files:**
- Create: `.github/workflows/ci-typescript.yml`

**Step 1: Create the workflow file**

```yaml
name: CI — TypeScript

on:
  push:
    branches: [main]
    paths:
      - "packages/typescript/**"
      - "examples/anip-ts/**"
      - ".github/workflows/ci-typescript.yml"
  pull_request:
    branches: [main]
    paths:
      - "packages/typescript/**"
      - "examples/anip-ts/**"
      - ".github/workflows/ci-typescript.yml"

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [20, 22]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}

      - name: Install workspace dependencies
        working-directory: packages/typescript
        run: npm ci

      - name: Build packages in dependency order
        working-directory: packages/typescript
        run: |
          npx tsc -p core/tsconfig.json
          npx tsc -p crypto/tsconfig.json
          npx tsc -p server/tsconfig.json
          npx tsc -p service/tsconfig.json
          npx tsc -p hono/tsconfig.json

      - name: Test @anip/core
        working-directory: packages/typescript
        run: npm test --workspace=@anip/core

      - name: Test @anip/crypto
        working-directory: packages/typescript
        run: npm test --workspace=@anip/crypto

      - name: Test @anip/server
        working-directory: packages/typescript
        run: npm test --workspace=@anip/server

      - name: Test @anip/service
        working-directory: packages/typescript
        run: npm test --workspace=@anip/service

      - name: Test @anip/hono
        working-directory: packages/typescript
        run: npm test --workspace=@anip/hono

      - name: Install and test TypeScript example
        working-directory: examples/anip-ts
        run: |
          npm install
          npm test
```

**Step 2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci-typescript.yml'))"
```

Expected: no error.

**Step 3: Commit**

```bash
git add .github/workflows/ci-typescript.yml
git commit -m "ci: add TypeScript CI workflow (Node 20, 22)"
```

---

### Task 4: Verify workflows run on GitHub

**Step 1: Push branch and create PR**

```bash
git checkout -b ci/package-ci
git push -u origin ci/package-ci
gh pr create --title "ci: add Python and TypeScript CI workflows" --body "..."
```

**Step 2: Check workflow runs**

```bash
gh run list --limit 5
```

Both `CI — Python` and `CI — TypeScript` should appear and start running.

**Step 3: Monitor for failures**

```bash
gh run watch
```

If any step fails, fix and push. Common issues:
- Missing dev dependencies in pyproject.toml
- npm ci failing because example lockfile is stale
- tsc build errors from missing built dependencies

**Step 4: Once green, report back**

All 4 matrix combinations should pass:
- Python 3.11 + 3.12
- Node 20 + 22
