# Studio Service-Shaping: Phase A+B Design Proposal

## What This Document Decides

This proposal locks the design for the product pivot from "ANIP capability validation" to "service shaping and contract shaping." It covers:

1. What is the minimum Shape artifact?
2. Is Approach/Proposal replaced, absorbed, or kept?
3. How do Services, Capabilities, and Domain Concepts relate?
4. What is user-authored vs Studio-derived?
5. How does evaluation consume the shape?
6. What does Phase A change in current evaluator wording/output?

---

## 1. The Shape Artifact

### Minimum Shape

A `Shape` is a first-class project artifact that describes the service architecture. It is user-authored (with Studio assistance) and replaces Proposal as the primary design artifact.

```yaml
shape:
  id: travel-estate-v1
  name: Travel Booking Estate
  type: multi_service    # single_service | multi_service
  
  services:
    - id: travel-search
      name: Travel Search
      role: planning
      responsibilities:
        - search available flights
        - compare options
        - present quotes
      capabilities:
        - search_flights
        - get_quote
      owns_concepts:
        - flight
        - quote
      
    - id: travel-booking
      name: Travel Booking
      role: execution
      responsibilities:
        - execute bookings
        - enforce budget constraints
        - manage payment
      capabilities:
        - book_flight
        - cancel_booking
      owns_concepts:
        - booking
        - passenger

  notes:
    - planning and booking are split because booking involves irreversible financial commitment
    - search service is read-only and can be scaled independently

  coordination:
    - from: travel-search
      to: travel-booking
      relationship: handoff
      description: search results flow to booking for execution

  domain_concepts:
    - id: flight
      name: Flight
      meaning: A specific flight option with route, carrier, and cost
      owner: travel-search
      sensitivity: none
    - id: quote
      name: Quote
      meaning: A priced travel option presented to the user
      owner: travel-search
      sensitivity: none
    - id: booking
      name: Booking
      meaning: A confirmed flight reservation with payment
      owner: travel-booking
      sensitivity: high
      risk_note: Irreversible financial commitment
    - id: passenger
      name: Passenger
      meaning: The person traveling
      owner: travel-booking
      sensitivity: none
```

### Single-Service Shape

For single-service designs, the shape is simpler:

```yaml
shape:
  id: devops-tool-v1
  name: DevOps Cluster Manager
  type: single_service

  services:
    - id: cluster-manager
      name: Cluster Manager
      role: execution
      responsibilities:
        - manage cluster lifecycle
        - deploy services
        - monitor health
      capabilities:
        - delete_cluster
        - deploy_service
        - get_deployment_status
      owns_concepts:
        - cluster
        - deployment

  domain_concepts:
    - id: cluster
      name: Cluster
      meaning: A production compute cluster
      owner: cluster-manager
      sensitivity: high
      risk_note: Deletion is irreversible
    - id: deployment
      name: Deployment
      meaning: A service deployment to a cluster
      owner: cluster-manager
      sensitivity: medium
```

### What the Shape Does NOT Include

- ANIP declared_surfaces (derived, not authored)
- Component lists (implementation detail)
- Anti-pattern warnings (evaluator output, not shape input)
- Transport bindings (infrastructure detail)
- Payload schemas or field-level data models

The shape stays at the "what services exist, what do they own, what do they do" level.

### Shape-Internal Integrity Validation

The JSON schema defines the structure, but the repository must enforce referential integrity within the shape on every create and update. These are hard validation rules (422 on violation):

| Rule | What it checks |
|------|---------------|
| `coordination[].from` and `coordination[].to` must reference existing `services[].id` | No coordination edges pointing to nonexistent services |
| `domain_concepts[].owner` must reference an existing `services[].id` or be `"shared"` | No orphaned concept ownership |
| `services[].owns_concepts[]` entries must reference existing `domain_concepts[].id` | No broken concept references |
| All IDs within a shape must be unique within their type | No duplicate service IDs, no duplicate concept IDs |

This is the same class of coherence problem that `assert_same_project()` solved at the project level — the repository validates the shape graph before accepting it.

---

## 2. Proposal → Shape Migration

### Decision: Proposal is absorbed into Shape

Proposal is not kept as a separate artifact. It is replaced by Shape.

**What moves into Shape:**
- `recommended_shape` → `shape.type` + `shape.services`
- `service_shapes` → `shape.services[].role` + responsibilities
- `rationale` → **kept on Shape** as a lightweight authored `notes` field. Users still need a place to say why this shape was chosen, what tradeoff it makes, or what constraint drove a boundary. This is not derivable from the evaluator.
- `required_components` → not in shape (implementation detail, can live in evaluator output)
- `optional_components` → not in shape
- `anti_pattern_warnings` → not in shape (evaluator output)
- `expected_glue_reduction` → not in shape (evaluator output)
- `declared_surfaces` → **derived from shape + requirements**, not user-authored

**What Proposal had that Shape replaces:**
- "What ANIP surfaces do we claim to handle?" → replaced by "What services exist, what do they own, and what must be exposed?"

**What Proposal had that becomes evaluator output:**
- Required components, anti-pattern warnings, expected glue reduction → the evaluator generates these from the shape + requirements + scenarios, not the user.

**What stays as user-authored on Shape:**
- Design rationale/notes — why this shape was chosen, what tradeoffs were made. Kept as `shape.notes: string[]` (optional). This is important for PM review and design history.

### Migration Path

- The `proposals` DB table remains but is deprecated. New projects create Shapes instead.
- Existing proposal data can be displayed read-only but is not the active design artifact.
- The ProposalView UI is kept for backward compatibility with existing projects but new projects don't create proposals.
- No data migration needed — proposals stay in the DB, shapes are new records.

### Database

```sql
CREATE TABLE shapes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_shapes_project ON shapes(project_id);
CREATE INDEX idx_shapes_requirements ON shapes(requirements_id);
```

The `data` column stores the full shape YAML/JSON. The `requirements_id` links the shape to the requirements it was designed against.

Evaluations gain a new optional `shape_id` reference (alongside the existing `proposal_id` which becomes optional for backward compatibility):

```sql
ALTER TABLE evaluations ADD COLUMN shape_id TEXT REFERENCES shapes(id);
ALTER TABLE evaluations ADD COLUMN shape_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN derived_expectations JSONB;
ALTER TABLE evaluations ALTER COLUMN proposal_id DROP NOT NULL;
```

- `shape_hash`: content hash of the shape at evaluation time (same pattern as `requirements_hash`/`proposal_hash`/`scenario_hash`)
- `derived_expectations`: snapshot of the contract expectations that were derived from shape + requirements at evaluation time. This ensures historical evaluations remain explainable even if the derivation rules change later. Without this, "stale" detection would be semantically incomplete — artifacts could be unchanged but derivation rules could evolve.

New evaluations use `shape_id`. Old evaluations keep their `proposal_id`.

---

## 3. Services, Capabilities, and Domain Concepts

### How They Relate

```
Shape
├── Services[]
│   ├── id, name, role
│   ├── responsibilities: string[]     (what this service does)
│   ├── capabilities: string[]         (what actions it exposes)
│   └── owns_concepts: string[]        (references to domain_concepts[].id)
│
├── Coordination[]                     (edges between services)
│   ├── from, to (service IDs)
│   ├── relationship: handoff | verification | async_followup
│   └── description
│
└── Domain Concepts[]
    ├── id, name, meaning
    ├── owner: service ID | "shared"
    ├── sensitivity: none | medium | high
    └── risk_note?: string
```

### What Each Layer Does

**Services** answer: "What compute boundaries exist?"
- Role: planning, execution, verification, monitoring, approval
- Responsibilities: free-text list of what the service does
- Capabilities: specific action names (map to scenario context.capability)

**Coordination** answers: "How do services relate?"
- Handoff: one service passes work to another
- Verification: one service verifies another's work
- Async followup: one service triggers later work in another

**Domain Concepts** answer: "What business objects does this system operate on?"
- Lightweight: just name, meaning, owner, sensitivity
- Not full schemas — intentionally thin
- Gives PMs business-readable language for service boundaries

### Capability ↔ Scenario Link

Scenario `context.capability` directly references capabilities in the shape. This is how scenarios pressure the shape — if a scenario references a capability that doesn't exist in any service, the evaluation flags it.

### Domain Concept ↔ Service Link

Each concept has an owner (a service ID or "shared"). This makes service boundaries legible: "travel-search owns Flights and Quotes; travel-booking owns Bookings and Passengers." A PM can immediately see what each service is responsible for.

---

## 4. User-Authored vs Studio-Derived

| Artifact | Authored By | Notes |
|----------|-------------|-------|
| Requirements | User (guided + advanced) | Unchanged from Slices 2-5 |
| Scenarios | User (guided + advanced) | Unchanged from Slices 2-5 |
| Shape | User (with Studio suggestions later) | Services, capabilities, responsibilities, domain concepts, coordination |
| Contract Expectations | **Studio-derived** | Derived from shape + requirements. "Given this shape and these requirements, these ANIP semantics must be exposed." |
| Evaluation | **Studio-derived** | "Does this shape support these scenarios?" |

### What "Studio-derived" Means for Contract Expectations

Contract expectations replace `declared_surfaces`. Instead of the user toggling 10 booleans, Studio looks at the shape and requirements and determines:

- This shape has a spending-possible service with budget constraints → budget_enforcement must be exposed
- This shape has cross-service handoff coordination → cross_service_handoff + cross_service_continuity must be exposed
- This shape has a high-risk capability → authority_posture must be exposed

The derivation is deterministic — based on structured rules, not LLM inference.

### What the User Still Controls

The user shapes the services, assigns capabilities, defines coordination edges. Studio tells them what that shape implies for contract semantics. The user can then adjust the shape if the implications are wrong or too expensive.

---

## 5. How Evaluation Consumes the Shape

### Current Model (Phase A — Transitional)

The evaluator continues to work with requirements + proposal + scenario. But its output language changes from surface-centric to shape-centric:

**Before (current):**
```
handled_by_anip: ["budget enforcement", "authority posture"]
glue_you_will_still_write: ["organization-specific approval workflow"]
what_would_improve: ["declare budget_enforcement surface"]
```

**After (Phase A):**
```
handled_by_anip: ["budget control via enforcement surface", "authority visibility"]
glue_you_will_still_write: ["organization-specific approval workflow integration"]
what_would_improve: ["the current design should expose budget enforcement to support spending-possible scenarios"]
```

The evaluator still checks the same things but its output is framed in terms of what the design should provide, not what ANIP features to enable. Phase A uses "current design" language (not "service shape") because the shape artifact doesn't exist yet.

### Target Model (Phase D — Full Shape-Support Evaluation)

The evaluator takes requirements + shape + scenario and asks:

1. Does this shape have a service with the capability referenced in the scenario?
2. Does that service have the right coordination edges for this scenario's cross-service expectations?
3. Do the requirements + shape together imply contract expectations that cover the scenario's needs?
4. What must change in the shape to support scenarios that aren't covered?

Output becomes:

```yaml
evaluation:
  scenario_name: book_flight_over_budget
  result: SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED
  
  shape_support:
    - capability: book_flight
      service: travel-booking
      status: found
    - expectation: budget_enforcement
      derived_from: requirements.business_constraints.spending_possible + shape has cost-bearing capability
      status: met
  
  shape_gaps:
    - gap: no approval boundary defined
      recommendation: add an approval coordination edge or assign approval responsibility to a service
    - gap: recovery posture not expressed in shape
      recommendation: assign recovery responsibility to travel-booking or add a recovery coordination edge
  
  glue_remaining:
    - organization-specific approval workflow (requires integration beyond ANIP)
```

This is far more useful than "declare more surfaces."

---

## 6. Phase A — Immediate Evaluator Changes

Phase A is the smallest step: reposition the evaluator's output language without changing the data model.

### What Changes

1. **Evaluator output wording** in `tooling/bin/anip_evaluator/`:
   - `handled_by_anip` entries reframe from "surface X" to "what the current design provides"
   - `what_would_improve` entries reframe from "declare surface X" to "the current design should expose X to support Y"
   - `why` entries explain in terms of design support, not feature lists
   - IMPORTANT: Phase A uses "current design" language, NOT "service shape" — the shape artifact doesn't exist yet

2. **EvaluationView** in Studio:
   - "Glue Gap Analysis" becomes "Design Support Analysis"
   - "Handled by ANIP" becomes "Supported by Design"
   - "Glue You Will Still Write" becomes "Requires Custom Integration"
   - "What Would Improve" becomes "Design Changes Needed" (not "Shape Changes" — no shape model yet)

3. **No data model changes** in Phase A. Proposals/declared_surfaces still work. This is a language/framing change only.

### What Does NOT Change in Phase A

- The evaluator's internal logic (same checks, same rules)
- The data model (no shape table yet)
- The API endpoints
- The project/artifact structure
- Existing tests (adjust expected strings only)

Phase A can ship as a single commit — it's evaluator output text + Vue view labels.

---

## 7. Phase B — Shape Model Implementation

Phase B adds the shape artifact and derived contract expectations.

### New Artifacts

1. **Shape** — first-class project artifact (DB table, API CRUD, Vue view)
2. **Derived Contract Expectations** — computed from shape + requirements (not stored, computed on read)

### New UI

- **ShapeView** — the primary design view, replacing ProposalView as the center of the workflow:
  - Service list with responsibilities, capabilities, domain concepts
  - Coordination edges (visual or tabular)
  - Derived contract expectations panel (read-only, shows what ANIP semantics the shape implies)
  - "This shape implies budget enforcement is needed" etc.

- **ProjectOverview** gains a "Shape" section alongside Requirements/Scenarios

### Guided Shape Flow

Like guided requirements and scenarios, the shape can have a guided mode:

- "How many services does this system need?" → single_service / multi_service
- "What does each service do?" → responsibilities
- "What actions does each service expose?" → capabilities (can pull from scenario context.capability)
- "What business objects does this system work with?" → domain concepts
- "How do services relate?" → coordination edges

### Evaluation Transition

During Phase B, the evaluator gains a new entry point:

```python
def evaluate_shape(requirements, shape, scenario) -> dict:
    """Evaluate scenario support against a shaped design."""
```

This runs alongside the existing `evaluate()` (which uses proposals). Projects with shapes use the new evaluator; legacy projects with proposals use the old one.

---

## 8. Schema

### Shape JSON Schema

```json
{
  "type": "object",
  "required": ["shape"],
  "properties": {
    "shape": {
      "type": "object",
      "required": ["id", "name", "type", "services"],
      "properties": {
        "id": { "type": "string", "minLength": 1 },
        "name": { "type": "string", "minLength": 1 },
        "type": { "type": "string", "enum": ["single_service", "multi_service"] },
        "notes": { "type": "array", "items": { "type": "string" } },
        "services": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "required": ["id", "name", "role"],
            "properties": {
              "id": { "type": "string" },
              "name": { "type": "string" },
              "role": { "type": "string" },
              "responsibilities": { "type": "array", "items": { "type": "string" } },
              "capabilities": { "type": "array", "items": { "type": "string" } },
              "owns_concepts": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "coordination": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["from", "to", "relationship"],
            "properties": {
              "from": { "type": "string" },
              "to": { "type": "string" },
              "relationship": { "type": "string", "enum": ["handoff", "verification", "async_followup"] },
              "description": { "type": "string" }
            }
          }
        },
        "domain_concepts": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "name", "meaning"],
            "properties": {
              "id": { "type": "string" },
              "name": { "type": "string" },
              "meaning": { "type": "string" },
              "owner": { "type": "string" },
              "sensitivity": { "type": "string", "enum": ["none", "medium", "high"] },
              "risk_note": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

---

## 9. Contract Expectation Derivation Rules

These are the deterministic rules for deriving what ANIP semantics a shape implies:

| If the shape + requirements show... | Then the design should expose... |
|--------------------------------------|--------------------------------|
| `business_constraints.spending_possible` + a service with cost-bearing capabilities | `budget_enforcement` |
| `business_constraints.cost_visibility_required` | `budget_enforcement` (implies cost visibility) |
| `business_constraints.approval_expected_for_high_risk` | `authority_posture` |
| `business_constraints.recovery_sensitive` | `recovery_class` |
| `permissions.preflight_discovery` | `authority_posture` |
| Multi-service shape with coordination edges | `cross_service_handoff` + `cross_service_continuity` |
| Coordination edge of type `verification` | `verify_via` |
| Coordination edge of type `async_followup` | `followup_via` |
| Any domain concept with `sensitivity: high` | `authority_posture` (high-sensitivity concepts need authority control) |
| `audit.durable` + `audit.cross_service_reconstruction_required` | `cross_service_reconstruction` |

These rules replace user-toggled `declared_surfaces`. The user shapes the services; Studio derives what semantics that shape requires.

---

## 10. Decision Summary

| Question | Decision |
|----------|----------|
| What is the minimum Shape artifact? | Services (id, name, role, responsibilities, capabilities, owns_concepts) + Coordination (edges) + Domain Concepts (id, name, meaning, owner, sensitivity) + Notes (authored design rationale) |
| Is Proposal replaced, absorbed, or kept? | Absorbed into Shape. Proposal table stays for backward compat, but new projects use shapes. declared_surfaces become derived, not authored. Rationale stays as user-authored notes on the shape. |
| How do Services, Capabilities, Domain Concepts relate? | Services own capabilities and concepts. Coordination defines edges between services. Concepts are business-readable anchors. All internal references validated by repository. |
| What is user-authored vs Studio-derived? | User: shape (services, capabilities, concepts, coordination, notes). Studio: contract expectations (derived from shape + requirements) and evaluation (shape support assessment). |
| How does evaluation consume the shape? | Phase A: same evaluator, reworded output. Phase D: new `evaluate_shape()` that checks capability presence, coordination coverage, derived expectation satisfaction. |
| What does Phase A change? | Evaluator output language only — "declare surface X" becomes "current design should expose X to support Y." Uses "current design" language, not "shape" (shape doesn't exist yet). No data model changes. |
| Evaluation provenance | Stored evaluations capture `shape_hash` + `derived_expectations` snapshot so historical evaluations remain explainable even if derivation rules evolve. |
| Shape-internal integrity | Repository validates all internal references (coordination edges → service IDs, concept ownership → service IDs, owns_concepts → concept IDs) on every create/update. 422 on violation. |
| Domain concepts scope | Intentionally lightweight: name, meaning, owner, sensitivity. No payload schemas, no field models. |
| Deterministic core | All derivation rules are structured and deterministic. No LLM required. |
