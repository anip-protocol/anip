# ANIP Studio: Design V2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Design mode a real validation engine — harden the evaluator, wire live validation into Studio, evaluate all 13 packs, and add `cross_service` to the glue category vocabulary.

**Architecture:** Vendor the tooling tree (evaluator, schemas, examples) from the codex repo into the ANIP repo. Harden the evaluator with scenario-type dispatch and honest advisory scoring. Add a thin FastAPI sidecar for live validation. Update Studio UI with "Run Validation" button. Regenerate all packs with evaluations.

**Tech Stack:** Python (evaluator + FastAPI), Vue 3 (Studio UI), Vite (dev proxy), Docker Compose (standalone)

**Proposal:** `docs/proposals/anip-studio-design-v2-proposal.md`

---

## File Structure

```
# Task 0: Vendor tooling into ANIP repo
tooling/                                      # COPY from codex repo
  bin/anip_design_validate.py
  schemas/*.schema.json
  examples/*/                                 # all 13 packs
  prompts/
  docs/
  README.md
  PROCESS.md
  NEXT_STEPS_PLAN.md
  VALIDATION_GATE.md
  VALIDATION_REPORT_TEMPLATE.md
  UI_AND_AUTOMATION_FLOW.md
  SCHEMA_EVOLUTION_V2.md

# Evaluator hardening
tooling/bin/anip_design_validate.py           # MODIFY: scenario-type dispatch, advisory scoring, v0.14-v0.19 rules

# Schema
tooling/schemas/evaluation.schema.json        # MODIFY: add cross_service to glue_category enum

# Evaluations
tooling/examples/*/evaluation.yaml            # CREATE for 10 missing packs, UPDATE 3 existing

# Validation API sidecar
studio/server/app.py                          # CREATE: FastAPI validation server
studio/server/requirements.txt                # CREATE: dependencies

# Studio UI
studio/src/views/EvaluationView.vue           # MODIFY: add "Run Validation" button + live indicator
studio/src/design/api.ts                      # CREATE: validation API client
studio/src/design/store.ts                    # MODIFY: add live evaluation state + loading
studio/src/design/types.ts                    # MODIFY: add cross_service to category type
studio/vite.config.ts                         # MODIFY: add /api proxy

# Regenerated packs
studio/src/design/data/packs.generated.ts     # UPDATE: regenerate with all evaluations
studio/scripts/build-design-packs.ts          # MODIFY: default source to tooling/examples/ (now in-repo)

# Docker (standalone)
studio/docker-compose.yml                     # CREATE: two-service compose (context: repo root)
studio/server/Dockerfile                      # CREATE: Python sidecar container (context: repo root)
studio/Dockerfile.standalone                  # CREATE: nginx + /api/ proxy to sidecar
studio/nginx-standalone.conf                  # CREATE: nginx config with /api/ proxy block

# Tests
tooling/tests/test_evaluator.py               # CREATE: evaluator regression tests
studio/server/test_api.py                     # CREATE: API endpoint tests
```

---

## Task 0: Vendor Tooling into ANIP Repo

**Files:**
- Create: `tooling/` (entire tree from codex)

- [ ] **Step 1: Copy tooling from codex**

```bash
cp -r /Users/samirski/Development/codex/ANIP/tooling /Users/samirski/Development/ANIP/tooling
```

Verify the key files exist:
- `tooling/bin/anip_design_validate.py`
- `tooling/schemas/evaluation.schema.json`
- `tooling/examples/travel-single/requirements.yaml`
- All 13 example pack directories

- [ ] **Step 2: Update build-design-packs.ts default source**

In `studio/scripts/build-design-packs.ts`, update the fallback source path from the non-existent `../../tooling/examples/` to the now-in-repo `../tooling/examples/` (relative to `studio/scripts/`), which resolves to `tooling/examples/` from the repo root.

- [ ] **Step 3: Verify pack regeneration works with in-repo source**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build:packs
```

Should work without `--source` now that tooling is in-repo.

- [ ] **Step 4: Commit**

```bash
cd /Users/samirski/Development/ANIP
git add tooling/ studio/scripts/build-design-packs.ts
git commit -m "feat: vendor tooling into ANIP repo (evaluator, schemas, examples, docs)"
```

---

## Task 1: Evaluation Schema — Add `cross_service` Category

**Files:**
- Modify: `tooling/schemas/evaluation.schema.json`
- Modify: `studio/src/design/types.ts`

- [ ] **Step 1: Add `cross_service` to evaluation schema**

In `tooling/schemas/evaluation.schema.json`, find the `glue_category` enum (currently `["safety", "orchestration", "observability"]`). Add `"cross_service"`.

- [ ] **Step 2: Update TypeScript types**

In `studio/src/design/types.ts`, if the category type is constrained, add `cross_service`.

- [ ] **Step 3: Commit**

```bash
git add tooling/schemas/ studio/src/design/types.ts
git commit -m "feat: add cross_service to evaluation glue_category vocabulary"
```

---

## Task 2: Harden the Evaluator

**Files:**
- Modify: `tooling/bin/anip_design_validate.py`

- [ ] **Step 1: Read the current evaluator**

Read `tooling/bin/anip_design_validate.py` to understand the existing `evaluate()` function.

- [ ] **Step 2: Add scenario-type dispatch**

Refactor `evaluate()` to dispatch based on `scenario.category`:

```python
CATEGORY_EVALUATORS = {
    "safety": evaluate_safety,
    "recovery": evaluate_recovery,
    "orchestration": evaluate_orchestration,
    "cross_service": evaluate_cross_service,
    "observability": evaluate_observability,
}

def evaluate(req, proposal, scenario):
    category = scenario["scenario"]["category"]
    evaluator = CATEGORY_EVALUATORS.get(category, evaluate_generic)
    return evaluator(req, proposal, scenario)
```

- [ ] **Step 3: Implement `evaluate_safety`**

Port the existing budget-overrun and permission-denial logic into `evaluate_safety`. Add checks for:
- Budget enforcement via `constraints.budget` (v0.13)
- Binding requirements (v0.13)
- Control requirements (v0.14)
- Non-delegable action handling (v0.15)

- [ ] **Step 4: Implement `evaluate_orchestration`**

New evaluator for orchestration scenarios. Check:
- Advisory composition hints (`refresh_via`, `verify_via` from v0.17)
- Cross-service handoff hints (`cross_service` block from v0.19)
- Recovery posture (`recovery_class` from v0.16)
- Whether the scenario's sequencing/handoff needs are met by protocol surfaces or still require wrappers

Key rule: advisory-only surfaces score as "protocol-assisted" (→ PARTIAL), not "protocol-handled" (→ HANDLED). A scenario that depends only on advisory hints for its core behavior should land at PARTIAL.

- [ ] **Step 5: Implement `evaluate_cross_service`**

Check:
- Cross-service continuity (`upstream_service`, `task_id` propagation from v0.18)
- Cross-service handoff hints (v0.19)
- Reconstruction quality (are `upstream_service` + `parent_invocation_id` + `task_id` all relevant?)

- [ ] **Step 6: Implement `evaluate_observability`**

Check:
- Audit requirements (durable, searchable)
- Lineage (task_id, parent_invocation_id)
- Cross-service reconstruction
- Whether the scenario's observability needs go beyond what the protocol provides

- [ ] **Step 7: Implement `evaluate_recovery`**

Check:
- Recovery class (v0.16)
- Resolution action vocabulary
- Refresh/verify paths (v0.17)
- Whether recovery guidance is enforceable or advisory-only

- [ ] **Step 8: Implement `evaluate_generic`**

Fallback for unknown categories. Conservative — defaults to PARTIAL with a note.

- [ ] **Step 9: Add honest advisory scoring throughout**

In all evaluators, apply these rules:
- Enforceable surfaces (binding checks, budget enforcement, permission discovery, control requirements) → credit as handled
- Advisory surfaces (refresh_via, verify_via, cross_service hints, recovery_class) → credit as "protocol-assisted" in the `why` section, do NOT auto-score as fully handled
- Add explicit glue items when the scenario's core behavior depends on advisory hints

- [ ] **Step 10: Write evaluator regression tests**

Create `tooling/tests/test_evaluator.py` with pytest:

```python
# Tests:
# - test_safety_scenario_budget_overrun → result is PARTIAL, not HANDLED
# - test_safety_scenario_denied → result is HANDLED
# - test_orchestration_scenario_advisory_only → result is PARTIAL (advisory hints don't auto-score HANDLED)
# - test_cross_service_scenario_advisory_only → result is PARTIAL
# - test_category_dispatch_routes_correctly → each category calls the right evaluator
# - test_handled_by_anip_contains_expected_surfaces → e.g. "permission discovery", "structured failure"
# - test_glue_items_are_concrete_not_vague → no glue item is shorter than 20 chars
# - test_unknown_category_falls_back_to_generic → unknown category → PARTIAL with note
```

Run:
```bash
cd /Users/samirski/Development/ANIP && python3 -m pytest tooling/tests/ -v
```

- [ ] **Step 11: Run against existing 3 evaluated packs and verify**

```bash
python3 tooling/bin/anip_design_validate.py \
  --requirements tooling/examples/travel-single/requirements.yaml \
  --proposal tooling/examples/travel-single/proposal.yaml \
  --scenario tooling/examples/travel-single/scenario.yaml
```

Compare output against existing `evaluation.yaml`. The result should be similar or stricter, not more generous.

- [ ] **Step 12: Commit**

```bash
git add tooling/bin/
git commit -m "feat: harden evaluator — scenario-type dispatch, advisory scoring, v0.14-v0.19 rules"
```

---

## Task 3: Evaluate All 13 Packs

**Files:**
- Create/Update: `tooling/examples/*/evaluation.yaml` (all 13 packs)

- [ ] **Step 1: Run the hardened evaluator on all 13 packs**

```bash
cd /Users/samirski/Development/ANIP
for pack in tooling/examples/*/; do
  name=$(basename "$pack")
  echo "=== Evaluating $name ==="
  python3 tooling/bin/anip_design_validate.py \
    --requirements "$pack/requirements.yaml" \
    --proposal "$pack/proposal.yaml" \
    --scenario "$pack/scenario.yaml" \
    --evaluation-out "$pack/evaluation.yaml"
done
```

Note: some packs may not have `proposal.yaml`. If so, the evaluator may need a fallback or those packs need proposals written first. Check which packs have all 3 inputs:

```bash
for d in tooling/examples/*/; do
  name=$(basename "$d")
  has_req="no"; [ -f "$d/requirements.yaml" ] && has_req="yes"
  has_prop="no"; [ -f "$d/proposal.yaml" ] && has_prop="yes"
  has_scen="no"; [ -f "$d/scenario.yaml" ] && has_scen="yes"
  echo "$name: req=$has_req prop=$has_prop scen=$has_scen"
done
```

If any packs are missing proposals, write minimal proposals for them (follow the pattern of existing proposals).

- [ ] **Step 2: Review evaluations for honesty**

Read each generated `evaluation.yaml`. Verify:
- Advisory-only scenarios do NOT get HANDLED
- Multi-service scenarios without enforceable cross-service controls get PARTIAL
- The `glue_you_will_still_write` is concrete and specific
- The `why` explains the reasoning clearly

- [ ] **Step 3: Regenerate Studio packs**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build:packs
```

Verify the generated file now has evaluations for all 13 packs.

- [ ] **Step 4: Commit**

```bash
git add tooling/examples/ studio/src/design/data/packs.generated.ts
git commit -m "feat: evaluate all 13 packs with hardened evaluator"
```

---

## Task 4: Validation API Sidecar

**Files:**
- Create: `studio/server/app.py`
- Create: `studio/server/requirements.txt`
- Modify: `studio/vite.config.ts`

- [ ] **Step 1: Create the FastAPI server**

Create `studio/server/app.py`:

```python
"""Thin validation API wrapping the ANIP evaluator."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys, os

# Add tooling to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tooling', 'bin'))
from anip_design_validate import evaluate, validate_payload, load_json
from pathlib import Path

app = FastAPI(title="ANIP Studio Validation API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "tooling" / "schemas"

class ValidateRequest(BaseModel):
    requirements: dict
    proposal: dict
    scenario: dict

@app.post("/api/validate")
async def validate_endpoint(req: ValidateRequest):
    # Validate inputs against schemas
    validate_payload(req.requirements, SCHEMA_DIR / "requirements.schema.json")
    validate_payload(req.proposal, SCHEMA_DIR / "proposal.schema.json")
    validate_payload(req.scenario, SCHEMA_DIR / "scenario.schema.json")

    # Run evaluation
    result = evaluate(req.requirements, req.proposal, req.scenario)

    # Validate output
    validate_payload(result, SCHEMA_DIR / "evaluation.schema.json")

    return result

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Create requirements.txt**

```
fastapi>=0.115.0
uvicorn>=0.32.0
pyyaml>=6.0
jsonschema>=4.23.0
```

- [ ] **Step 3: Add Vite dev proxy**

In `studio/vite.config.ts`, add proxy config:

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8100',
      changeOrigin: true,
    },
  },
},
```

- [ ] **Step 4: Write API tests**

Create `studio/server/test_api.py` using FastAPI's TestClient (no server needed):

```python
from fastapi.testclient import TestClient
from .app import app
import yaml
from pathlib import Path

client = TestClient(app)

# Tests:
# - test_health_returns_ok
# - test_validate_travel_single → returns evaluation with result in (HANDLED, PARTIAL, REQUIRES_GLUE)
# - test_validate_invalid_input → returns 422 or 400
# - test_validate_response_has_required_fields → scenario_name, result, handled_by_anip, etc.
```

Run:
```bash
cd /Users/samirski/Development/ANIP && python3 -m pytest studio/server/test_api.py -v
```

- [ ] **Step 5: Test the sidecar manually**

```bash
# Terminal 1: start the API server
cd /Users/samirski/Development/ANIP
pip install -r studio/server/requirements.txt
uvicorn studio.server.app:app --port 8100

# Terminal 2: test
curl -s http://localhost:8100/api/health
```

- [ ] **Step 6: Commit**

```bash
git add studio/server/ studio/vite.config.ts
git commit -m "feat(studio): add validation API sidecar (FastAPI on :8100)"
```

---

## Task 5: Studio UI — Live Validation

**Files:**
- Create: `studio/src/design/api.ts`
- Modify: `studio/src/design/store.ts`
- Modify: `studio/src/views/EvaluationView.vue`

- [ ] **Step 1: Create validation API client**

Create `studio/src/design/api.ts`:

```typescript
import type { Evaluation } from './types'

const API_BASE = '/api'

export async function runValidation(
  requirements: Record<string, any>,
  proposal: Record<string, any>,
  scenario: Record<string, any>,
): Promise<Evaluation> {
  const resp = await fetch(`${API_BASE}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirements, proposal, scenario }),
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`Validation failed: ${err}`)
  }
  return resp.json()
}

export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_BASE}/health`)
    return resp.ok
  } catch {
    return false
  }
}
```

- [ ] **Step 2: Update design store with live validation state**

In `studio/src/design/store.ts`, add:

```typescript
liveEvaluation: null as Evaluation | null,
validating: false,
validationError: string | null,
apiAvailable: false,
```

Add functions:
- `runLiveValidation()` — calls API, sets `liveEvaluation`
- `checkApiAvailability()` — pings health endpoint, sets `apiAvailable`

- [ ] **Step 3: Update EvaluationView with Run Validation button**

In `EvaluationView.vue`:
- Add "Run Validation" button in the header (only shown when `apiAvailable` is true)
- Add loading spinner while `validating` is true
- Add a "Live result" / "Pre-computed result" indicator badge
- When live evaluation exists, display it instead of the static one
- Add a "Reset to pre-computed" button to switch back

- [ ] **Step 4: Check API availability on Design mode entry**

When entering Design mode, call `checkApiAvailability()`. If the API is down, the "Run Validation" button is hidden — the UI gracefully falls back to static evaluations.

- [ ] **Step 5: Build and verify**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add studio/src/design/ studio/src/views/EvaluationView.vue
git commit -m "feat(studio): add live validation — Run Validation button + API client"
```

---

## Task 6: Docker Compose for Standalone

**Files:**
- Create: `studio/docker-compose.yml`
- Create: `studio/server/Dockerfile`
- Create: `studio/nginx-standalone.conf`

- [ ] **Step 1: Create Python sidecar Dockerfile**

Build context is the repo root so all COPY paths are relative to repo root:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY studio/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY studio/server/ server/
COPY tooling/ /app/tooling/
ENV PYTHONPATH=/app
EXPOSE 8100
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8100"]
```

- [ ] **Step 2: Create nginx-standalone.conf**

Create `studio/nginx-standalone.conf` — same as existing `nginx.conf` but with `/api/` proxy:

```nginx
# ... existing location / block for serving static files ...

location /api/ {
    proxy_pass http://studio-api:8100;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Copy the existing `studio/nginx.conf` as the base, then add the `/api/` proxy block.

- [ ] **Step 3: Create docker-compose.yml**

Build context for BOTH services is the repo root (one level up from `studio/`):

```yaml
version: '3.8'
services:
  studio-web:
    build:
      context: ..
      dockerfile: studio/Dockerfile.standalone
    ports:
      - "8080:8080"
    depends_on:
      - studio-api

  studio-api:
    build:
      context: ..
      dockerfile: studio/server/Dockerfile
    expose:
      - "8100"
```

Note: `studio-web` uses a separate `Dockerfile.standalone` that copies `nginx-standalone.conf` instead of `nginx.conf`. The API container only exposes 8100 internally (not on host) — nginx proxies to it.

Create `studio/Dockerfile.standalone` — same as existing `studio/Dockerfile` but in the serve stage, use `nginx-standalone.conf`:
```dockerfile
COPY nginx-standalone.conf /etc/nginx/nginx.conf
```

- [ ] **Step 4: Test compose locally**

```bash
cd /Users/samirski/Development/ANIP/studio && docker compose up --build
```

Verify:
- `http://localhost:8080/` serves Studio
- `http://localhost:8080/api/health` returns ok (proxied through nginx)
- Live validation works from the UI

- [ ] **Step 5: Commit**

```bash
git add studio/docker-compose.yml studio/server/Dockerfile
git commit -m "feat(studio): add Docker Compose for standalone deployment (web + API sidecar)"
```

---

## Task 7: Build + Polish

- [ ] **Step 1: Full Studio build**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build
```

- [ ] **Step 2: Verify all Design views with new evaluations**

- All 13 packs show evaluations (no "Not yet available")
- Evaluation results feel honest (advisory-only scenarios at PARTIAL)
- Categories include `cross_service` where relevant
- "Run Validation" appears when API is up, hidden when down
- Live results display correctly with indicator badge

- [ ] **Step 3: Verify Inspect mode still works**

Existing protocol inspector unchanged.

- [ ] **Step 4: Commit**

```bash
git add studio/
git commit -m "feat(studio): Design V2 complete — hardened evaluator + live validation"
```
