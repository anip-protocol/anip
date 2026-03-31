# ANIP v0.13: Budget, Binding, and Control Requirements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add enforceable budget constraints, execution-time binding requirements, and control requirement declarations to ANIP — making the protocol able to express and enforce pre-execution conditions, not just describe them.

**Architecture:** Three additions work together: (1) `token.constraints.budget` carries an enforceable cost ceiling in the delegation chain, (2) `requires_binding` on capabilities declares that a bound reference (quote, offer) must be present at invoke time, (3) `control_requirements` vocabulary distinguishes informational from enforceable pre-conditions. Budget enforcement uses the bound price when bindings exist, making budget + binding reinforce each other.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + Protobuf + JSON Schema + Vue (Studio)

**Spec:** `docs/proposals/v0.13-slice1-spec-draft.md`

---

## File Structure

```
# Spec and Schema
SPEC.md                                         # MODIFY: §4.3 constraints.budget, §4.1 requires_binding + control_requirements, §6.3 token issuance + invoke enforcement
schema/anip.schema.json                         # MODIFY: add Budget, FinancialCost, BindingRequirement, ControlRequirement types
proto/anip/v1/anip.proto                        # MODIFY: add budget to token issuance, binding/control to capability

# Python (reference implementation)
packages/python/anip-core/src/anip_core/models.py              # MODIFY: FinancialCost model, Budget model, DelegationConstraints.budget, CapabilityDeclaration.requires_binding + control_requirements, RestrictedCapability.unmet_token_requirements
packages/python/anip-server/src/anip_server/delegation.py      # MODIFY: budget in token, budget narrowing enforcement
packages/python/anip-server/src/anip_server/permissions.py     # MODIFY: unmet_token_requirements in permission discovery
packages/python/anip-service/src/anip_service/service.py       # MODIFY: budget pre-check, binding check, control requirement check in invoke
packages/python/anip-fastapi/src/anip_fastapi/routes.py        # MODIFY: extract budget from token issuance request
packages/python/anip-grpc/src/anip_grpc/server.py             # MODIFY: extract budget from gRPC token issuance
packages/python/anip-stdio/src/anip_stdio/server.py           # MODIFY: extract budget from stdio token issuance
packages/python/anip-service/tests/test_budget.py              # CREATE: budget enforcement tests
packages/python/anip-service/tests/test_binding.py             # CREATE: binding requirement tests
packages/python/anip-service/tests/test_control_requirements.py # CREATE: control requirement tests

# TypeScript
packages/typescript/core/src/models.ts                         # MODIFY: add FinancialCost, Budget, BindingRequirement, ControlRequirement interfaces
packages/typescript/server/src/delegation.ts                   # MODIFY: budget in token, budget narrowing
packages/typescript/service/src/service.ts                     # MODIFY: budget/binding/control enforcement in invoke
packages/typescript/server/src/permissions.ts                  # MODIFY: unmet_token_requirements in discovery
packages/typescript/rest/src/routes.ts                         # MODIFY: extract budget from token issuance
packages/typescript/express/src/routes.ts                      # MODIFY: extract budget from token issuance
packages/typescript/fastify/src/routes.ts                      # MODIFY: extract budget from token issuance
packages/typescript/hono/src/routes.ts                         # MODIFY: extract budget from token issuance
packages/typescript/stdio/src/server.ts                        # MODIFY: extract budget from stdio token issuance

# Go
packages/go/core/models.go                                    # MODIFY: add FinancialCost, Budget, BindingRequirement, ControlRequirement structs
packages/go/server/delegation.go                               # MODIFY: budget in token, budget narrowing
packages/go/service/invoke.go                                  # MODIFY: budget/binding/control enforcement
packages/go/service/permissions.go                             # MODIFY: unmet_token_requirements
packages/go/httpapi/handler.go                                 # MODIFY: extract budget from token issuance
packages/go/ginapi/handler.go                                  # MODIFY: extract budget from token issuance
packages/go/grpcapi/server.go                                  # MODIFY: extract budget from gRPC token issuance
packages/go/stdioapi/server.go                                 # MODIFY: extract budget from stdio token issuance

# Java
packages/java/anip-core/src/main/java/dev/anip/core/FinancialCost.java      # CREATE
packages/java/anip-core/src/main/java/dev/anip/core/Budget.java             # CREATE
packages/java/anip-core/src/main/java/dev/anip/core/BindingRequirement.java  # CREATE
packages/java/anip-core/src/main/java/dev/anip/core/ControlRequirement.java  # CREATE
packages/java/anip-core/src/main/java/dev/anip/core/CapabilityDeclaration.java # MODIFY: add requires_binding, control_requirements
packages/java/anip-core/src/main/java/dev/anip/core/DelegationConstraints.java # MODIFY: add budget
packages/java/anip-core/src/main/java/dev/anip/core/PermissionResponse.java   # MODIFY: add unmet_token_requirements to nested RestrictedCapability class
packages/java/anip-server/src/main/java/dev/anip/server/DelegationEngine.java  # MODIFY: budget in token
packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java     # MODIFY: enforcement
packages/java/anip-rest/src/main/java/dev/anip/rest/RestRouter.java            # MODIFY: extract budget
packages/java/anip-stdio/src/main/java/dev/anip/stdio/AnipStdioServer.java    # MODIFY: extract budget from stdio token issuance

# C#
packages/csharp/src/Anip.Core/FinancialCost.cs                # CREATE
packages/csharp/src/Anip.Core/Budget.cs                        # CREATE
packages/csharp/src/Anip.Core/BindingRequirement.cs            # CREATE
packages/csharp/src/Anip.Core/ControlRequirement.cs            # CREATE
packages/csharp/src/Anip.Core/CapabilityDeclaration.cs         # MODIFY: add requires_binding, control_requirements
packages/csharp/src/Anip.Core/DelegationConstraints.cs         # MODIFY: add budget
packages/csharp/src/Anip.Core/RestrictedCapability.cs          # MODIFY: add unmet_token_requirements
packages/csharp/src/Anip.Server/DelegationEngine.cs            # MODIFY: budget in token
packages/csharp/src/Anip.Service/AnipService.cs                # MODIFY: enforcement
packages/csharp/src/Anip.Rest/RestRouter.cs                    # MODIFY: extract budget
packages/csharp/src/Anip.Stdio/AnipStdioServer.cs             # MODIFY: extract budget from stdio token issuance

# Conformance
conformance/test_budget.py                     # CREATE: budget enforcement conformance tests
conformance/test_binding.py                    # CREATE: binding requirement conformance tests
conformance/test_control_requirements.py       # CREATE: control requirement conformance tests

# Studio
studio/src/components/InvokeResult.vue         # MODIFY: show budget_context
studio/src/views/AuditView.vue                 # MODIFY: show budget/binding context in entries
studio/src/views/ManifestView.vue              # MODIFY: show requires_binding and control_requirements

# Showcase
examples/showcase/travel/capabilities.py       # MODIFY: add requires_binding to book_flight, add quote_id to search results
examples/showcase/travel/data.py               # MODIFY: add quote_id generation to search results

# Website
website/docs/protocol/reference.md             # MODIFY: add budget, binding, control requirement sections
website/docs/protocol/capabilities.md          # MODIFY: add requires_binding and control_requirements docs
```

---

## Task 1: Spec, Schema, and Proto Updates

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`
- Modify: `proto/anip/v1/anip.proto`

- [ ] **Step 1: Update SPEC.md**

a) §4.3 (Delegation Chain): Add `budget` to `DelegationConstraints`:
```yaml
constraints:
  max_delegation_depth: 3
  concurrent_branches: allowed
  budget:
    currency: USD
    max_amount: 500
```

Add budget narrowing rule: child budget MUST NOT exceed parent budget.

b) §4.1 (Capability Declaration): Add `requires_binding` and `control_requirements` to capability schema.

c) §6.3 (Invocation): Add budget enforcement rule (pre-execution MUST reject). Add invocation-request `budget` as a negotiation hint — token budget is the ceiling, invocation hint can be lower but never higher. Remove scope-string budget convention entirely (pre-1.0, no backward compat needed). Add `budget_context` to both success and failure responses when a budget was evaluated.

d) §6.3 (Token Issuance): Add `budget` to token issuance request.

e) Add new failure types: `budget_exceeded`, `budget_currency_mismatch`, `budget_not_enforceable`, `binding_missing`, `binding_stale`, `control_requirement_unsatisfied`.

f) §6.3 (Permission Discovery): Add `unmet_token_requirements` to restricted capabilities in `/anip/permissions` response. Only token-evaluable requirements (`cost_ceiling`, `stronger_delegation_required`) are included — invoke-evaluable ones (`bound_reference`, `freshness_window`) are checked at invoke time.

- [ ] **Step 2: Update JSON Schema**

Add `FinancialCost`, `Budget`, `BindingRequirement`, `ControlRequirement` type definitions. Add `budget` to `DelegationConstraints`. Add `requires_binding` and `control_requirements` to `CapabilityDeclaration`. Add `unmet_token_requirements` to `RestrictedCapability`.

- [ ] **Step 3: Update gRPC proto**

Add `Budget` and `FinancialCost` messages. Add `budget` field to token issuance request/response. Add `requires_binding` and `control_requirements` to capability-related messages if applicable.

- [ ] **Step 4: Commit**

```bash
git add SPEC.md schema/anip.schema.json proto/anip/v1/anip.proto
git commit -m "spec: add budget constraints, binding requirements, and control requirements (v0.13)"
```

---

## Task 2: Python Core Models

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`

- [ ] **Step 1: Add FinancialCost model**

Replace untyped `dict[str, Any]` with a structured model. The existing `Cost.financial` field must change from `dict[str, Any] | None` to `FinancialCost | None`:

```python
class FinancialCost(BaseModel):
    currency: str
    amount: float | None = None        # for fixed costs
    range_min: float | None = None     # for estimated costs
    range_max: float | None = None     # for estimated costs
    typical: float | None = None       # for estimated costs
    upper_bound: float | None = None   # for dynamic costs
```

Update `Cost`:
```python
class Cost(BaseModel):
    certainty: CostCertainty = CostCertainty.FIXED
    financial: FinancialCost | None = None  # was dict[str, Any] | None
    determined_by: str | None = None
    factors: list[str] | None = None
    compute: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None
```

Update `CostActual`:
```python
class CostActual(BaseModel):
    financial: FinancialCost  # was dict[str, Any]
    variance_from_estimate: str | None = None
```

**Migration:** Update all existing dict-style `financial={"currency": "USD", "amount": 100}` usages across showcase apps, tests, and examples to use `FinancialCost(currency="USD", amount=100)`.

- [ ] **Step 2: Add Budget model**

```python
class Budget(BaseModel):
    currency: str
    max_amount: float
```

- [ ] **Step 3: Add budget to DelegationConstraints**

```python
class DelegationConstraints(BaseModel):
    max_delegation_depth: int = 3
    concurrent_branches: ConcurrentBranches = ConcurrentBranches.ALLOWED
    budget: Budget | None = None
```

- [ ] **Step 4: Add BindingRequirement model**

```python
class BindingRequirement(BaseModel):
    type: str  # "quote", "offer", "price_lock"
    field: str  # which param must carry the reference
    source_capability: str | None = None  # advisory
    max_age: str | None = None  # ISO 8601 duration, e.g. "PT15M"
```

- [ ] **Step 5: Add ControlRequirement model**

```python
class ControlRequirement(BaseModel):
    type: str  # "cost_ceiling", "bound_reference", "freshness_window", "stronger_delegation_required"
    field: str | None = None  # for bound_reference and freshness_window (which param to check)
    max_age: str | None = None  # for freshness_window
    enforcement: str = "reject"  # v0.13: "reject" only; "warn" deferred to future slice
```

- [ ] **Step 6: Add to CapabilityDeclaration**

```python
class CapabilityDeclaration(BaseModel):
    # ... existing fields ...
    requires_binding: list[BindingRequirement] = Field(default_factory=list)
    control_requirements: list[ControlRequirement] = Field(default_factory=list)
```

- [ ] **Step 7: Add unmet_token_requirements to RestrictedCapability**

```python
class RestrictedCapability(BaseModel):
    capability: str
    reason: str
    grantable_by: str
    unmet_token_requirements: list[str] = Field(default_factory=list)
```

- [ ] **Step 8: Fix all dict-style financial cost usages**

Search for `financial={` and `financial=dict(` across all Python packages and examples. Replace with `FinancialCost(...)`. Also update any `financial.get("currency")` or `financial["currency"]` access patterns to `financial.currency`.

Key locations:
- `examples/showcase/travel/capabilities.py` — book_flight, search_flights cost declarations
- `examples/showcase/finance/capabilities.py` — trade cost declarations
- `packages/python/anip-service/src/anip_service/service.py` — cost_actual handling
- `packages/python/anip-graphql/src/anip_graphql/translation.py` — financial cost translation
- Test files with cost declarations

- [ ] **Step 9: Run existing tests to verify FinancialCost migration**

```bash
pytest packages/python/ -x -v
```

- [ ] **Step 10: Commit**

```bash
git add packages/python/ examples/
git commit -m "feat(python): add FinancialCost, Budget, BindingRequirement, ControlRequirement models (v0.13)"
```

---

## Task 3: Python Delegation Engine — Budget in Tokens

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/delegation.py`
- Modify: `packages/python/anip-server/src/anip_server/permissions.py`
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/python/anip-grpc/src/anip_grpc/server.py`
- Modify: `packages/python/anip-stdio/src/anip_stdio/server.py`

- [ ] **Step 1: Accept budget in token issuance**

In `delegation.py` `issue_root_token()` and `delegate()`: read `budget` from the request, create `Budget` object, add to `DelegationConstraints`.

In `_create_token()`: accept `budget` parameter, include in JWT `constraints` claims.

In all transport adapters (`routes.py`, `server.py` for gRPC and stdio): extract `budget` from the token issuance request body, pass to service.

- [ ] **Step 2: Enforce budget narrowing**

In `delegate()`: if parent token has `constraints.budget`, child budget MUST NOT exceed it. Reject with `ANIPFailure(type="budget_exceeded", ...)` if child tries to widen.

```python
if parent_constraints and parent_constraints.budget:
    if child_budget is None:
        # Child inherits parent budget
        child_budget = parent_constraints.budget
    elif child_budget.max_amount > parent_constraints.budget.max_amount:
        raise ANIPFailure(type="budget_exceeded", detail=f"Child budget ${child_budget.max_amount} exceeds parent budget ${parent_constraints.budget.max_amount}")
    elif child_budget.currency != parent_constraints.budget.currency:
        raise ANIPFailure(type="budget_currency_mismatch", detail=f"Child budget currency {child_budget.currency} does not match parent {parent_constraints.budget.currency}")
```

- [ ] **Step 3: Include budget in JWT claims**

In `_create_token()`: add `budget` to the JWT `constraints` claims so it's available at invoke time.

- [ ] **Step 4: Echo budget in token issuance response**

Return `budget` in the issuance response dict.

- [ ] **Step 5: Add unmet_token_requirements to permission discovery**

In `permissions.py` `discover_permissions()`: when checking capabilities, if a capability declares `control_requirements` with token-evaluable types (`cost_ceiling`, `stronger_delegation_required`), check whether the token satisfies them. If not, add to `restricted` with `unmet_token_requirements`:

```python
# After scope matching, check token-evaluable control requirements
unmet = []
for req in decl.control_requirements:
    if req.type == "cost_ceiling" and (not constraints or not constraints.budget):
        unmet.append("cost_ceiling")
    elif req.type == "stronger_delegation_required":
        # Check if token has explicit capability binding
        if not token_has_explicit_capability_binding:
            unmet.append("stronger_delegation_required")

if unmet and any(r.enforcement == "reject" for r in decl.control_requirements if r.type in unmet):
    restricted.append(RestrictedCapability(
        capability=name,
        reason=f"missing control requirements: {', '.join(unmet)}",
        grantable_by=root_principal,
        unmet_token_requirements=unmet,
    ))
```

- [ ] **Step 6: Run existing tests + commit**

```bash
pytest packages/python/ -x -v
git add packages/python/
git commit -m "feat(python): budget in delegation tokens with narrowing enforcement (v0.13)"
```

---

## Task 4: Python Invoke — Budget, Binding, and Control Enforcement

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Create: `packages/python/anip-service/tests/test_budget.py`
- Create: `packages/python/anip-service/tests/test_binding.py`
- Create: `packages/python/anip-service/tests/test_control_requirements.py`

- [ ] **Step 1: Add `_resolve_bound_price()` helper**

```python
def _resolve_bound_price(
    decl: CapabilityDeclaration, params: dict[str, Any]
) -> float | None:
    """Extract the bound price from invocation params using the capability's binding declarations.

    Looks at the capability's requires_binding to find a binding field in params,
    then extracts the price from the bound value. The bound value is expected to be
    a dict with an embedded 'price' key, or the service resolves it internally.

    For protocol purposes, the service determines the price associated with a binding
    reference (this is an implementation detail per the spec).
    """
    for binding in decl.requires_binding:
        if binding.field in params and params[binding.field] is not None:
            bound_value = params[binding.field]
            # Implementation-specific: extract price from bound reference
            # The service knows how to look up the quoted price for this binding ID
            if isinstance(bound_value, dict) and "price" in bound_value:
                return float(bound_value["price"])
            # If binding is a string ID, the service resolves price from its own store
            # This is service-internal logic, not protocol-level
    return None
```

- [ ] **Step 2: Add budget pre-check in `_invoke_body()`**

After delegation validation, before handler execution:

```python
# Determine effective budget (token budget is ceiling, invocation hint can be lower)
effective_budget = None
if token.constraints and token.constraints.budget:
    effective_budget = token.constraints.budget
    # Invocation-level budget hint: use min of token and request hint
    if request_budget is not None:
        if request_budget.currency != effective_budget.currency:
            return failure("budget_currency_mismatch", ...)
        effective_budget = Budget(
            currency=effective_budget.currency,
            max_amount=min(effective_budget.max_amount, request_budget.max_amount),
        )

# Budget enforcement
if effective_budget:
    decl = cap.declaration
    if decl.cost and decl.cost.financial:
        if decl.cost.financial.currency != effective_budget.currency:
            return failure("budget_currency_mismatch", ...)

        # Determine check amount based on certainty
        check_amount: float | None = None

        if decl.cost.certainty == "fixed":
            check_amount = decl.cost.financial.amount

        elif decl.cost.certainty == "estimated":
            # Estimated costs require a binding to be enforceable
            if decl.requires_binding:
                bound_price = _resolve_bound_price(decl, params)
                if bound_price is not None:
                    check_amount = bound_price
                # If binding is required but not yet provided,
                # the binding_missing check (below) will catch it
            else:
                # No requires_binding on capability — budget cannot be enforced
                return failure("budget_not_enforceable",
                    detail=f"Capability {decl.name} has estimated cost but no requires_binding — budget cannot be reliably enforced",
                    resolution={"action": "obtain_quote_first", "requires": "invoke a search capability to get a bound price"})

        elif decl.cost.certainty == "dynamic":
            check_amount = decl.cost.financial.upper_bound

        if check_amount is not None and check_amount > effective_budget.max_amount:
            return failure("budget_exceeded",
                detail=f"Cost ${check_amount} exceeds budget ${effective_budget.max_amount}",
                budget_context={
                    "budget_max": effective_budget.max_amount,
                    "budget_currency": effective_budget.currency,
                    "cost_check_amount": check_amount,
                    "cost_certainty": decl.cost.certainty,
                })
```

- [ ] **Step 3: Add binding presence check**

Before handler execution, check `requires_binding`:

```python
for binding in decl.requires_binding:
    if binding.field not in params or params[binding.field] is None:
        return failure("binding_missing",
            detail=f"Capability {decl.name} requires '{binding.field}' (type: {binding.type})",
            resolution={"action": "obtain_binding",
                        "requires": f"invoke {binding.source_capability or 'source capability'} to obtain a {binding.field}"})
    if binding.max_age:
        age = _resolve_binding_age(params[binding.field])
        if age and age > _parse_duration(binding.max_age):
            return failure("binding_stale",
                detail=f"Binding '{binding.field}' has exceeded max_age of {binding.max_age}",
                resolution={"action": "refresh_binding",
                            "requires": f"invoke {binding.source_capability or 'source capability'} again for a fresh {binding.field}"})
```

- [ ] **Step 4: Add control requirement check**

Check `control_requirements` — all are `reject` enforcement in v0.13:

```python
for req in decl.control_requirements:
    satisfied = True

    if req.type == "cost_ceiling":
        satisfied = effective_budget is not None
    elif req.type == "bound_reference":
        satisfied = req.field is not None and req.field in params and params[req.field] is not None
    elif req.type == "freshness_window":
        if req.field and req.field in params:
            age = _resolve_binding_age(params[req.field])
            max_age = _parse_duration(req.max_age) if req.max_age else None
            satisfied = age is None or max_age is None or age <= max_age
        else:
            satisfied = False
    elif req.type == "stronger_delegation_required":
        satisfied = token_has_explicit_capability_binding

    if not satisfied:
        return failure("control_requirement_unsatisfied",
            detail=f"Capability {decl.name} requires {req.type}",
            unsatisfied_requirements=[req.type])
```

- [ ] **Step 5: Add budget_context and binding_context to audit entries**

Include in audit entry data when budget or binding was involved:

```python
audit_extra = {}
if effective_budget:
    audit_extra["budget_context"] = {
        "budget_max": effective_budget.max_amount,
        "budget_currency": effective_budget.currency,
        "cost_actual": cost_actual.financial.amount if cost_actual else None,
        "within_budget": (cost_actual.financial.amount <= effective_budget.max_amount) if cost_actual and cost_actual.financial.amount else True,
    }
if decl.requires_binding:
    audit_extra["binding_context"] = {
        "bindings_required": [b.field for b in decl.requires_binding],
        "bindings_provided": [b.field for b in decl.requires_binding if b.field in params],
    }
```

- [ ] **Step 6: Write budget tests**

Create `test_budget.py`:
- `test_budget_enforcement_fixed_cost` — token budget $100, fixed cost $50 → success
- `test_budget_exceeded_fixed_cost` — token budget $30, fixed cost $50 → rejected with `budget_exceeded`
- `test_budget_narrowing_child_within` — child $300 from parent $500 → success
- `test_budget_narrowing_child_exceeds` — child $600 from parent $500 → rejected
- `test_budget_currency_mismatch` — USD budget, EUR cost → rejected with `budget_currency_mismatch`
- `test_budget_not_enforceable` — estimated cost, no requires_binding → rejected with `budget_not_enforceable`
- `test_budget_with_bound_price_within` — estimated cost with binding, bound price $280, budget $500 → success
- `test_budget_with_bound_price_exceeds` — estimated cost with binding, bound price $550, budget $500 → rejected
- `test_budget_dynamic_upper_bound` — dynamic cost with upper_bound $200, budget $300 → success
- `test_budget_invocation_hint_lower` — token budget $500, invocation hint $300, cost $250 → success (effective budget $300)
- `test_budget_invocation_hint_higher_ignored` — token budget $500, invocation hint $800 → effective budget stays $500
- `test_budget_context_in_response` — budget_context included in successful invocation response

- [ ] **Step 7: Write binding tests**

Create `test_binding.py`:
- `test_binding_present_succeeds` — required field present → success
- `test_binding_missing_rejected` — required field absent → `binding_missing`
- `test_binding_stale_rejected` — binding older than max_age → `binding_stale`
- `test_binding_no_max_age_no_staleness_check` — binding present, no max_age → success regardless of age

- [ ] **Step 8: Write control requirement tests**

Create `test_control_requirements.py`:
- `test_cost_ceiling_required_with_budget` — cost_ceiling requirement + token has budget → success
- `test_cost_ceiling_required_without_budget` — cost_ceiling requirement + no budget → `control_requirement_unsatisfied`
- `test_bound_reference_required_present` — bound_reference requirement + field present → success
- `test_bound_reference_required_missing` — bound_reference requirement + field missing → `control_requirement_unsatisfied`
- `test_freshness_window_within` — freshness_window requirement + binding within max_age → success
- `test_freshness_window_exceeded` — freshness_window requirement + binding older than max_age → `control_requirement_unsatisfied`
- `test_unmet_token_requirements_in_permissions` — cost_ceiling requirement, no budget in token → capability shows in `restricted` with `unmet_token_requirements`

- [ ] **Step 9: Run all Python tests**

```bash
pytest packages/python/ -x -v
```

- [ ] **Step 10: Commit**

```bash
git add packages/python/
git commit -m "feat(python): budget, binding, and control requirement enforcement in invoke (v0.13)"
```

---

## Task 5: TypeScript Runtime

**Files:**
- Modify: `packages/typescript/core/src/models.ts` — add `FinancialCost`, `Budget`, `BindingRequirement`, `ControlRequirement` interfaces; update `Cost.financial` from `Record<string, unknown>` to `FinancialCost`; add `requiresBinding`, `controlRequirements` to `CapabilityDeclaration`; add `unmetTokenRequirements` to `RestrictedCapability`
- Modify: `packages/typescript/server/src/delegation.ts` — budget in token issuance, budget narrowing enforcement
- Modify: `packages/typescript/service/src/service.ts` — budget pre-check with invocation hint precedence, binding presence/staleness check, control requirement check; audit extensions
- Modify: `packages/typescript/server/src/permissions.ts` — `unmetTokenRequirements` in permission discovery for token-evaluable controls
- Modify: `packages/typescript/rest/src/routes.ts` — extract budget from token issuance request body
- Modify: `packages/typescript/express/src/routes.ts` — extract budget from token issuance request body
- Modify: `packages/typescript/fastify/src/routes.ts` — extract budget from token issuance request body
- Modify: `packages/typescript/hono/src/routes.ts` — extract budget from token issuance request body
- Modify: `packages/typescript/stdio/src/server.ts` — extract budget from stdio token issuance

- [ ] **Step 1: Add models to `core/src/models.ts`**

Add `FinancialCost` interface with `currency`, `amount?`, `rangeMin?`, `rangeMax?`, `typical?`, `upperBound?`. Add `Budget` interface. Add `BindingRequirement` and `ControlRequirement` interfaces. Update `Cost.financial` to `FinancialCost | null`. Add `requiresBinding` and `controlRequirements` to `CapabilityDeclaration`. Add `unmetTokenRequirements` to `RestrictedCapability`.

Fix all existing `financial: { currency: "USD", amount: 100 }` usages across TypeScript packages and examples.

- [ ] **Step 2: Add budget to delegation with narrowing**

In `delegation.ts`: accept `budget` in token issuance, include in JWT claims, enforce narrowing (child ≤ parent).

- [ ] **Step 3: Add enforcement in invoke**

In `service.ts`: add budget pre-check (effective budget = min of token budget and invocation hint), binding presence/staleness check, control requirement check. Add `budgetContext` and `bindingContext` to audit entries.

- [ ] **Step 4: Add permission discovery extension**

In `server/src/permissions.ts`: add `unmetTokenRequirements` to restricted capabilities for token-evaluable control requirements.

- [ ] **Step 5: Extract budget in all transport adapters**

In all routes files and stdio server: extract `budget` from token issuance request body, pass to service.

- [ ] **Step 6: Run tests**

```bash
cd packages/typescript && npx vitest run
```

- [ ] **Step 7: Commit**

```bash
git add packages/typescript/
git commit -m "feat(typescript): budget, binding, and control requirement enforcement (v0.13)"
```

---

## Task 6: Go Runtime

**Files:**
- Modify: `packages/go/core/models.go` — add `FinancialCost`, `Budget`, `BindingRequirement`, `ControlRequirement` structs; update `Cost.Financial` from `map[string]any` to `*FinancialCost`; add `RequiresBinding`, `ControlRequirements` to `CapabilityDeclaration`; add `UnmetTokenRequirements` to `RestrictedCapability`
- Modify: `packages/go/server/delegation.go` — budget in token, narrowing
- Modify: `packages/go/service/invoke.go` — budget/binding/control enforcement
- Modify: `packages/go/service/permissions.go` — `UnmetTokenRequirements` in discovery
- Modify: `packages/go/httpapi/handler.go` — extract budget from token issuance
- Modify: `packages/go/ginapi/handler.go` — extract budget from token issuance
- Modify: `packages/go/grpcapi/server.go` — extract budget from gRPC token issuance
- Modify: `packages/go/stdioapi/server.go` — extract budget from stdio token issuance

- [ ] **Step 1: Add models to `core/models.go`**

Add Go structs matching the spec. Use `json:",omitempty"` tags for optional fields. Fix all existing `map[string]any` financial cost usages.

- [ ] **Step 2: Budget in delegation with narrowing**

- [ ] **Step 3: Enforcement in invoke**

- [ ] **Step 4: Permission discovery extension**

- [ ] **Step 5: Extract budget in all transport handlers (HTTP, Gin, gRPC, stdio)**

- [ ] **Step 6: Regenerate gRPC Go code from updated proto**

```bash
cd packages/go && go generate ./...
```

- [ ] **Step 7: Run tests**

```bash
cd packages/go && go test ./...
```

- [ ] **Step 8: Commit**

```bash
git add packages/go/
git commit -m "feat(go): budget, binding, and control requirement enforcement (v0.13)"
```

---

## Task 7: Java Runtime

**Files:**
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/FinancialCost.java`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/Budget.java`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/BindingRequirement.java`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/ControlRequirement.java`
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/CapabilityDeclaration.java` — add `requiresBinding`, `controlRequirements` fields
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/DelegationConstraints.java` — add `budget` field
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/PermissionResponse.java` — add `unmetTokenRequirements` to nested `RestrictedCapability` class
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/Cost.java` — change `financial` from `Map<String,Object>` to `FinancialCost`
- Modify: `packages/java/anip-server/src/main/java/dev/anip/server/DelegationEngine.java` — budget in token, narrowing
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java` — enforcement
- Modify: `packages/java/anip-rest/src/main/java/dev/anip/rest/RestRouter.java` — extract budget
- Modify: `packages/java/anip-rest-spring/src/main/java/dev/anip/rest/spring/AnipRestController.java` — extract budget
- Modify: `packages/java/anip-rest-quarkus/src/main/java/dev/anip/rest/quarkus/AnipRestResource.java` — extract budget
- Modify: `packages/java/anip-stdio/src/main/java/dev/anip/stdio/AnipStdioServer.java` — extract budget from stdio

- [ ] **Step 1: Create new model classes**

Create `FinancialCost`, `Budget`, `BindingRequirement`, `ControlRequirement` as Java records or classes matching the spec.

- [ ] **Step 2: Update existing models**

Update `Cost.java` to use `FinancialCost`. Add fields to `CapabilityDeclaration`, `DelegationConstraints`. Add `unmetTokenRequirements` to the nested `RestrictedCapability` class inside `PermissionResponse.java` (NOT a standalone file).

- [ ] **Step 3: Budget in delegation with narrowing**

- [ ] **Step 4: Enforcement in invoke (Spring + Quarkus)**

- [ ] **Step 5: Permission discovery extension**

- [ ] **Step 6: Extract budget in all adapters (REST, Spring, Quarkus, stdio)**

- [ ] **Step 7: Run tests**

```bash
cd packages/java && mvn test
```

- [ ] **Step 8: Commit**

```bash
git add packages/java/
git commit -m "feat(java): budget, binding, and control requirement enforcement (v0.13)"
```

---

## Task 8: C# Runtime

**Files:**
- Create: `packages/csharp/src/Anip.Core/FinancialCost.cs`
- Create: `packages/csharp/src/Anip.Core/Budget.cs`
- Create: `packages/csharp/src/Anip.Core/BindingRequirement.cs`
- Create: `packages/csharp/src/Anip.Core/ControlRequirement.cs`
- Modify: `packages/csharp/src/Anip.Core/CapabilityDeclaration.cs` — add `RequiresBinding`, `ControlRequirements`
- Modify: `packages/csharp/src/Anip.Core/DelegationConstraints.cs` — add `Budget`
- Modify: `packages/csharp/src/Anip.Core/RestrictedCapability.cs` — add `UnmetTokenRequirements`
- Modify: `packages/csharp/src/Anip.Core/Cost.cs` — change `Financial` from `Dictionary<string,object>` to `FinancialCost`
- Modify: `packages/csharp/src/Anip.Server/DelegationEngine.cs` — budget in token, narrowing
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs` — enforcement
- Modify: `packages/csharp/src/Anip.Rest/RestRouter.cs` — extract budget
- Modify: `packages/csharp/src/Anip.Rest.AspNetCore/AnipRestController.cs` — extract budget
- Modify: `packages/csharp/src/Anip.Stdio/AnipStdioServer.cs` — extract budget from stdio

- [ ] **Step 1: Create new model classes**

Create C# records or classes for `FinancialCost`, `Budget`, `BindingRequirement`, `ControlRequirement`.

- [ ] **Step 2: Update existing models**

Update `Cost.cs` to use `FinancialCost`. Add properties to `CapabilityDeclaration`, `DelegationConstraints`, `RestrictedCapability`.

- [ ] **Step 3: Budget in delegation with narrowing**

- [ ] **Step 4: Enforcement in invoke**

- [ ] **Step 5: Permission discovery extension**

- [ ] **Step 6: Extract budget in all adapters (REST, AspNetCore, stdio)**

- [ ] **Step 7: Run tests**

```bash
cd packages/csharp && dotnet test
```

- [ ] **Step 8: Commit**

```bash
git add packages/csharp/
git commit -m "feat(csharp): budget, binding, and control requirement enforcement (v0.13)"
```

---

## Task 9: Conformance Suite

**Files:**
- Create: `conformance/test_budget.py`
- Create: `conformance/test_binding.py`
- Create: `conformance/test_control_requirements.py`
- Modify: `conformance/conftest.py`

- [ ] **Step 1: Update conftest.py**

Extend `issue_token()` to accept `budget` parameter. Add `issue_token_with_budget()` helper:

```python
def issue_token_with_budget(client, budget_currency, budget_max_amount, **kwargs):
    return issue_token(client, budget={"currency": budget_currency, "max_amount": budget_max_amount}, **kwargs)
```

- [ ] **Step 2: Budget conformance tests**

Create `test_budget.py`:
- Token issuance with budget echoes it back in response
- Invoke with budget-bound token and fixed-cost capability within budget → success
- Invoke with budget-bound token exceeding cost → `budget_exceeded`
- Budget narrowing in delegation chain — child ≤ parent
- Currency mismatch rejection
- Dynamic cost with upper_bound within budget → success

- [ ] **Step 3: Binding conformance tests**

Create `test_binding.py`:
- Invoke capability with `requires_binding` but missing field → `binding_missing`
- Invoke with binding field present → success

- [ ] **Step 4: Control requirement conformance tests**

Create `test_control_requirements.py`:
- Invoke capability with `cost_ceiling` requirement but no budget in token → `control_requirement_unsatisfied`
- Permission discovery returns `unmet_token_requirements` for capabilities with unsatisfied token-evaluable requirements

- [ ] **Step 5: Commit**

```bash
git add conformance/
git commit -m "test: add budget, binding, and control requirement conformance tests (v0.13)"
```

---

## Task 10: Travel Showcase — Quote Binding

**Files:**
- Modify: `examples/showcase/travel/capabilities.py`
- Modify: `examples/showcase/travel/data.py`

- [ ] **Step 1: Add quote_id to search results**

When `search_flights` returns results, include a `quote_id` per flight with an embedded timestamp (e.g. `qt-{hex8}-{unix_ts}`).

- [ ] **Step 2: Add requires_binding to book_flight**

```python
requires_binding=[
    BindingRequirement(
        type="quote",
        field="quote_id",
        source_capability="search_flights",
        max_age="PT15M",
    ),
],
```

- [ ] **Step 3: Add budget to capability cost declarations**

Ensure book_flight has `FinancialCost` declaration with proper estimated cost fields for the binding enforcement to work:

```python
cost=Cost(
    certainty=CostCertainty.ESTIMATED,
    financial=FinancialCost(
        currency="USD",
        range_min=280,
        range_max=500,
        typical=420,
    ),
    determined_by="search_flights",
),
```

- [ ] **Step 4: Test locally**

```bash
cd examples/showcase && python -m pytest -x -v
```

- [ ] **Step 5: Commit**

```bash
git add examples/showcase/
git commit -m "feat(showcase): add quote binding to travel example (v0.13)"
```

---

## Task 11: Studio UI Updates

**Files:**
- Modify: `studio/src/components/InvokeResult.vue`
- Modify: `studio/src/views/AuditView.vue`
- Modify: `studio/src/views/ManifestView.vue`

- [ ] **Step 1: Show budget_context in InvokeResult**

Display budget max, cost check amount, and within_budget status when `budget_context` is present in the response.

- [ ] **Step 2: Show binding info in manifest capability cards**

Display `requires_binding` declarations in the capability card: type, field name, source capability, max_age.

- [ ] **Step 3: Show control_requirements in manifest**

Display control requirements with enforcement level (reject/warn) badge.

- [ ] **Step 4: Show budget/binding context in audit entries**

In `AuditView.vue`, display `budget_context` and `binding_context` fields when present.

- [ ] **Step 5: Build, test, sync**

```bash
cd studio && npx vitest run && cd .. && bash studio/sync.sh
```

- [ ] **Step 6: Commit**

```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): show budget, binding, and control requirements in UI (v0.13)"
```

---

## Task 12: Website Documentation

**Files:**
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/protocol/capabilities.md`

- [ ] **Step 1: Update protocol reference**

Add sections for:
- `constraints.budget` in token issuance — currency, max_amount, narrowing rule
- Budget enforcement rule — pre-execution check, invocation hint precedence
- New failure types — `budget_exceeded`, `budget_currency_mismatch`, `budget_not_enforceable`, `binding_missing`, `binding_stale`, `control_requirement_unsatisfied`
- `requires_binding` in capability declaration
- `control_requirements` in capability declaration
- `unmet_token_requirements` in permission discovery

- [ ] **Step 2: Update capabilities page**

Add sections on:
- Binding requirements — what they are, when to use them, how they reinforce budget enforcement
- Control requirements — token-evaluable vs invoke-evaluable, enforcement levels
- Examples showing the complete flow: search → get quote → book with binding under budget

- [ ] **Step 3: Commit**

```bash
git add website/
git commit -m "docs: add budget, binding, and control requirement documentation (v0.13)"
```

---

## Task 13: Version Bump and Release

- [ ] **Step 1: Update protocol version to 0.13 in SPEC.md and discovery defaults**
- [ ] **Step 2: Commit**

```bash
git add SPEC.md packages/
git commit -m "chore: bump protocol version to 0.13"
```

- [ ] **Step 3: Trigger release workflow with version `0.13.0`**
