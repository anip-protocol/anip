# ANIP Studio: Design V2 — Design Proposal

## 1. V2 Goal

Make Design mode a real validation engine, not just an artifact viewer. V1 proved the product shell. V2 makes the judgments trustworthy and the validation live.

**Four deliverables, in priority order:**
1. Hardened evaluator with stricter scoring
2. Live validation from the Studio UI
3. Evaluation schema improvements (careful, minimal)
4. All 13 packs evaluated (not just 3)

---

## 2. Repo Boundary: Vendor Tooling into ANIP Repo

### Decision

The evaluator, schemas, and example packs currently live in the separate codex repo (`/Users/samirski/Development/codex/ANIP/tooling/`). V2 vendors them into the ANIP repo under `tooling/`.

**Why:** Studio's build script, live validation server, and CI all need these artifacts. Keeping them in a separate repo creates a broken dependency chain — Studio can't build packs without codex, CI can't run the evaluator without codex, and contributors can't reproduce the validation flow.

**V2 Task 0:** Copy `tooling/` from codex into the ANIP repo. This includes `bin/`, `schemas/`, `examples/`, `prompts/`, and `docs/`. The codex copy becomes the archive; the ANIP repo copy becomes the source of truth.

---

## 3. Evaluator Hardening

### Current State

The evaluator (`tooling/bin/anip_design_validate.py`) is ~200 lines of rules-based Python. It checks for specific requirements flags and pattern-matches on scenario context. It has two main weaknesses:

1. **Advisory surfaces auto-score as handled.** Multi-service scenarios get `"cross-service task identity continuity"`, `"independent but linkable audit records"`, `"cleaner service handoff"` added to `handled_by_anip` just because `is_multi_service` is true (lines 116-120). No check that the actual advisory hints (`refresh_via`, `verify_via`, `cross_service`, `upstream_service`) are declared or useful.

2. **Only two scenario patterns are coded.** The evaluator has explicit logic for `permissions_state == "denied"` (safe refusal) and `over_budget` (budget overrun). Everything else falls through to generic output. The 10 unevaluated packs cover recovery, refresh, verification, handoff, fan-out, and async follow-up — none of which the evaluator can score.

### What to Fix

#### a) Add evaluation rules for v0.14-v0.19 protocol surfaces

The evaluator needs rules for:
- **Budget enforcement** (v0.13): check if `requires_binding`, `control_requirements`, `budget` are in the proposal
- **Authority posture** (v0.15): check if `reason_type`, `resolution_hint`, `non_delegable_action` are relevant
- **Recovery posture** (v0.16): check if `recovery_class` is relevant for the scenario's failure path
- **Advisory composition** (v0.17): check if `refresh_via`, `verify_via` are declared
- **Cross-service continuity** (v0.18): check if `upstream_service`, task_id propagation rules are relevant
- **Cross-service handoff** (v0.19): check if `cross_service` block with `handoff_to`, `refresh_via`, `verify_via`, `followup_via` are declared

#### b) Distinguish protocol-handled vs protocol-assisted vs wrapper-dependent

Add an internal classification before assigning the top-level result:

| Classification | Meaning | Maps to |
|---|---|---|
| `protocol-handled` | The protocol surface itself removes the glue | Contributes to HANDLED |
| `protocol-assisted` | The protocol helps (advisory hints, visibility) but wrappers still do decisive work | Contributes to PARTIAL |
| `wrapper-dependent` | The protocol surface is too thin, teams must rebuild the logic | Contributes to REQUIRES_GLUE |

This classification stays internal to the evaluator — it informs the result but doesn't change the external schema. Each `handled_by_anip` item gets a mental classification:
- Enforceable surfaces (budget enforcement, binding checks, permission discovery) → protocol-handled
- Advisory surfaces (refresh_via, verify_via, cross_service hints) → protocol-assisted
- Missing surfaces → wrapper-dependent

#### c) Score advisory hints honestly

Advisory-only surfaces should NOT auto-score as fully handled. The evaluator should:
- Credit advisory hints as "protocol-assisted" (improves decision quality, doesn't enforce)
- Only credit as "protocol-handled" when enforcement is in place (binding checks, budget enforcement, etc.)
- Explicitly note in `glue_you_will_still_write` when the protocol hints but doesn't enforce

#### d) Add scenario-type dispatch

Instead of the current two-path `if permissions_state == "denied"` / `if over_budget` structure, add a dispatch based on scenario category and pressure area:

```python
EVALUATORS = {
    "safety": evaluate_safety_scenario,
    "recovery": evaluate_recovery_scenario,
    "orchestration": evaluate_orchestration_scenario,
    "cross_service": evaluate_cross_service_scenario,
    "observability": evaluate_observability_scenario,
}
```

Each evaluator checks the relevant protocol surfaces for that pressure area.

### Implementation Approach

The evaluator stays as a single Python script. No external dependencies beyond `yaml` and `jsonschema`. The improvements are:
- More rules checking more protocol surfaces
- Internal classification logic
- Scenario-type dispatch
- Honest advisory scoring

---

## 4. Live Validation in Studio

### Current State

Design V1 displays pre-computed evaluation YAML. There's no way to run the evaluator from the UI.

### What to Build

Add a "Run Validation" button to the Design sidebar or Evaluation view that:
1. Takes the active pack's requirements + proposal + scenario
2. Sends them to a validation endpoint
3. Receives the evaluation result
4. Updates the Evaluation view with fresh results

### Architecture Options

**Option A: Sidecar Python service (preferred for V2)**

Add a thin Python HTTP server that wraps the existing evaluator:

```
POST /api/validate
Body: { requirements, proposal, scenario }
Response: { evaluation }
```

The server is a ~50-line FastAPI app that calls `evaluate()` from the existing script. It runs as a **separate process** (sidecar), not inside the nginx static container.

**Development:** Two processes — `npm run dev` (Vite on :5173) + `python -m studio.server` (FastAPI on :8100). Vite proxies `/api/*` to the Python server.

**Standalone Docker:** A `docker-compose.yml` with two services:
- `studio-web`: nginx serving the built Vue app (same as today's Dockerfile)
- `studio-api`: Python FastAPI validation server

The current `studio/Dockerfile` (nginx-only) stays untouched for embedded Inspect builds.

**Option B: In-browser validation (deferred)**

Port the evaluator to TypeScript and run in-browser. More complex, deferred to V3+.

### Studio UI Changes

- Add "Run Validation" button to the Evaluation view header
- Show loading state while validation runs
- Replace the static evaluation data with the live result
- Keep the ability to view pre-computed evaluations for packs that have them
- Add a visual indicator: "Live result" vs "Pre-computed result"

### Validation API Shape

```typescript
// studio/src/design/api.ts
export async function runValidation(
  requirements: Requirements,
  proposal: Proposal,
  scenario: Scenario,
): Promise<Evaluation> {
  const resp = await fetch('/api/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirements, proposal, scenario }),
  })
  return resp.json()
}
```

---

## 5. Evaluation Schema Improvements

### Current Schema

The evaluation schema has flat string arrays for `handled_by_anip`, `glue_you_will_still_write`, and `glue_category`. Categories are evaluation-wide, not per-glue-item.

### V2 Changes (Minimal, Careful)

#### a) Add `cross_service` to glue_category enum

Current: `["safety", "orchestration", "observability"]`
V2: `["safety", "orchestration", "observability", "cross_service"]`

This was already noted in `tooling/SCHEMA_EVOLUTION_V2.md`.

#### b) Add optional `severity` to evaluation

```yaml
evaluation:
  severity: high | medium | low
```

Indicates how critical the remaining glue is. A `PARTIAL` with `severity: low` means "almost handled, minor wrapper remains." A `PARTIAL` with `severity: high` means "significant glue still required."

#### c) Keep glue items as flat strings for V2

Per-item category tagging is tempting but not justified yet. The evaluator doesn't produce per-item categories reliably. Keep them flat. Reconsider in V3 if the evaluator evolves to produce structured glue items.

---

## 6. Evaluate All 13 Packs

### Current State

Only 3/13 packs have evaluations. The other 10 show "Not yet available" in Studio.

### What to Do

Run the hardened evaluator against all 13 packs. Commit the evaluation YAML for each. This:
- Makes every pack browsable end-to-end in Studio
- Tests the hardened evaluator against real scenarios
- Produces honest Glue Gap Analysis for recovery, refresh, verification, handoff, fan-out, and async follow-up scenarios

### Expected Results

Most of the 10 new evaluations should land at PARTIAL — the protocol has advisory surfaces for these scenarios but doesn't enforce. If the hardened evaluator gives HANDLED for advisory-only scenarios, it's still too soft.

---

## 7. V2 Scope vs Deferred

### V2 (this build)

- Vendor tooling into ANIP repo (Task 0)
- Hardened evaluator with scenario-type dispatch (safety, recovery, orchestration, cross_service, observability) + honest advisory scoring
- `cross_service` glue category added to schema
- Optional `severity` on evaluation
- Live validation from Studio (Python FastAPI sidecar, NOT embedded in nginx container)
- All 13 packs evaluated
- "Run Validation" button in Studio UI
- Live vs pre-computed result indicator
- Vite dev proxy for `/api/*` to sidecar
- Docker compose for standalone deployment (studio-web + studio-api)

### Deferred to V3+

- Per-glue-item category tagging (needs evaluator to produce structured items first)
- Requirements/scenario editing in Studio
- Legacy comparison mode
- Starter pack generation
- Scenario suite formalization (stable IDs, pressure areas)
- Agent workflows
- Multi-user / persistence backend
- WASM-based in-browser validation

---

## 8. File Changes

```
# Task 0: Vendor tooling into ANIP repo
tooling/                                      # CREATE: copy from codex repo (bin/, schemas/, examples/, prompts/, docs/)

# Evaluator improvements
tooling/bin/anip_design_validate.py           # MODIFY: add scenario-type dispatch, advisory scoring, v0.14-v0.19 rules

# Schema
tooling/schemas/evaluation.schema.json        # MODIFY: add cross_service to glue_category, add optional severity

# Evaluations for all packs
tooling/examples/*/evaluation.yaml            # CREATE/UPDATE: run hardened evaluator on all 13 packs

# Validation API server (sidecar)
studio/server/app.py                          # CREATE: FastAPI app wrapping evaluate()
studio/server/requirements.txt                # CREATE: fastapi, uvicorn, pyyaml, jsonschema

# Studio UI
studio/src/views/EvaluationView.vue           # MODIFY: add "Run Validation" button, live/pre-computed indicator
studio/src/design/api.ts                      # CREATE: validation API client
studio/src/design/store.ts                    # MODIFY: add live evaluation state
studio/src/design/types.ts                    # MODIFY: add severity to Evaluation type

# Vite dev proxy
studio/vite.config.ts                         # MODIFY: add /api proxy to Python sidecar

# Regenerated packs
studio/src/design/data/packs.generated.ts     # UPDATE: regenerate with new evaluations
studio/scripts/build-design-packs.ts          # MODIFY: update source path to tooling/examples/ (now in-repo)

# Docker (standalone only — embedded Dockerfile untouched)
studio/docker-compose.yml                     # CREATE: two-service compose (studio-web + studio-api)
studio/server/Dockerfile                      # CREATE: Python validation server container
```

---

## 9. Success Criteria

V2 is successful if:

- The evaluator gives PARTIAL (not HANDLED) for advisory-only scenarios
- All 13 packs have evaluations that feel honest when read
- Users can run validation from the Studio UI
- The Glue Gap Analysis is more discriminating than V1 (stricter threshold)
- The evaluation severity signal helps distinguish "almost handled" from "major gap"
- The product feels like a validation engine, not just an artifact viewer
