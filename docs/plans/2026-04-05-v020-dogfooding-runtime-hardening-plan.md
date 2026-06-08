# ANIP Runtime Hardening: Dogfooding Ergonomics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two most immediate runtime friction points Studio dogfooding exposed: (1) sync/async bug in Python's bootstrap auth hook and (2) poor ergonomics for capability-targeted token issuance.

**Architecture:** Two changes across all 5 runtimes (Python, TypeScript, Go, Java, C#). Part 1: fix the Python auth hook bug (silently accepts coroutine as principal), document sync-only contract in Go/Java/C#, TypeScript already correct. Part 2: add `issueCapabilityToken()` convenience helpers to all runtimes. Both are additive SDK-level changes — no protocol wire-format changes, no version bump.

**Tech Stack:** Python (FastAPI, async), TypeScript (Node), Go, Java (Maven), C# (.NET)

---

## Scope

This plan covers two runtime ergonomics improvements:

1. **Bootstrap auth hook contract** — fix the Python async bug, document sync-only contract in Go/Java/C#
2. **Capability-targeted token issuance** — add `issueCapabilityToken()` helpers to all runtimes

### What This Is NOT

This is **not a protocol version bump**. The protocol version stays at `anip/0.19`. These are SDK-level convenience additions and a bug fix — no wire-format changes, no new protocol semantics, no schema changes.

### Auth Hook Contract

The runtime-library policy is: **runtimes MUST support at least synchronous bootstrap auth hooks.** Async support is language-dependent:
- Python: supports both sync and async hooks (fixing a real bug where async hooks were silently broken)
- TypeScript: already supports both sync and async hooks correctly
- Go/Java/C#: sync-only by language design — documented clearly

This is honest about language differences, not a divergence.

### issueCapabilityToken Scope Rules

The `issueCapabilityToken()` helper pre-binds the `capability` field on a token. It does **NOT** default `scope` — scope must be explicitly provided by the caller. Capability names and scope strings are different things (e.g., capability `evaluate_service_design` may need scope `studio.workbench.evaluate_service_design`). The helper prevents `purpose_mismatch` errors by correctly setting `capability`, but it does not guess scope.

### Root Issuance Only

This slice's `issueCapabilityToken()` covers **root token issuance only**. It does NOT accept `parent_token`, `subject`, or `caller_class` — those are delegation-flow fields.

**Why:** The `parent_token` field has inconsistent meaning across runtimes — some treat it as a JWT string, others look it up by stored token ID. Wrapping that inconsistency in a new convenience helper would bake the mismatch into a first-class API. Delegation ergonomics should be addressed in a follow-on slice that first resolves the `parent_token` semantics, then adds a delegation-aware helper.

## File Structure

### Per-Runtime Changes

Each runtime needs 2 changes:
1. Auth hook fix/documentation
2. `issueCapabilityToken()` helper (root issuance only)

| Runtime | Service File | Tests |
|---------|-------------|-------|
| Python | `packages/python/anip-service/src/anip_service/service.py` | `packages/python/anip-service/tests/` |
| TypeScript | `packages/typescript/service/src/service.ts` | `packages/typescript/service/tests/` |
| Go | `packages/go/service/service.go` | `packages/go/service/service_test.go` |
| Java | `packages/java/anip-service/.../ANIPService.java` | `packages/java/anip-service/src/test/` |
| C# | `packages/csharp/src/Anip.Service/AnipService.cs` | `packages/csharp/test/` |

---

## Task 1: Python — Fix Async Auth Hook Bug + Add issueCapabilityToken

The Python runtime has a real bug: the `authenticate` hook is called synchronously inside an async method. If someone passes an async function, the coroutine object is truthy and silently becomes the "principal" string. This task fixes it and adds the capability token helper.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`

- [ ] **Step 1: Fix the auth hook to support both sync and async**

In `service.py`, update the `authenticate_bearer` method. Currently it does:
```python
principal = self._authenticate(bearer_value)
```

Change to properly detect and await async hooks:
```python
import inspect

# In authenticate_bearer():
if self._authenticate:
    result = self._authenticate(bearer_value)
    if inspect.isawaitable(result):
        principal = await result
    else:
        principal = result
```

Also update the type hint on the `authenticate` parameter in `__init__`:
```python
from typing import Callable, Awaitable, Union

authenticate: Callable[[str], Union[str, None, Awaitable[str | None]]] | None = None
```

- [ ] **Step 2: Add issueCapabilityToken helper**

Add a convenience method to `ANIPService`:
```python
async def issue_capability_token(
    self,
    principal: str,
    capability: str,
    scope: list[str],
    *,
    purpose_parameters: dict | None = None,
    ttl_hours: int = 2,
    budget: dict | None = None,
) -> dict:
    """Issue a root token pre-bound to a specific capability.
    
    scope must be explicitly provided — capability names and scope strings
    are different things (e.g. capability 'evaluate_service_design' may
    need scope 'studio.workbench.evaluate_service_design').
    
    This helper covers root issuance only. For delegation flows
    (parent_token, subject, caller_class), use issue_token() directly
    until parent_token semantics are resolved across runtimes.
    """
    request: dict = {
        "subject": principal,
        "capability": capability,
        "scope": scope,
        "ttl_hours": ttl_hours,
    }
    if purpose_parameters:
        request["purpose_parameters"] = purpose_parameters
    if budget:
        request["budget"] = budget
    return await self.issue_token(principal, request)
```

- [ ] **Step 3: Add tests**

Add test for async auth hook:
```python
# Test that async authenticate hooks are properly awaited
async def test_async_bootstrap_auth_hook():
    async def async_auth(bearer: str) -> str | None:
        return "async-principal" if bearer == "valid" else None
    
    service = ANIPService(
        service_id="test",
        authenticate=async_auth,
        ...
    )
    result = await service.authenticate_bearer("valid")
    assert result == "async-principal"
```

Add test for sync auth hook still works:
```python
def test_sync_bootstrap_auth_hook():
    def sync_auth(bearer: str) -> str | None:
        return "sync-principal" if bearer == "valid" else None
    
    service = ANIPService(
        service_id="test",
        authenticate=sync_auth,
        ...
    )
    # sync hook called in async context should still work
```

Add test for `issue_capability_token`:
```python
async def test_issue_capability_token():
    # Should produce a token bound to the specified capability
    # Invoking with a different capability should fail with purpose_mismatch
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/samirski/Development/ANIP && python3 -m pytest packages/python/anip-service/tests/ -v 2>&1 | tail -20`

- [ ] **Step 5: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(python): fix async auth hook bug + add issue_capability_token helper"
```

---

## Task 2: TypeScript — Add issueCapabilityToken

TypeScript already handles async auth hooks correctly. Only needs the helper.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`

- [ ] **Step 1: Add issueCapabilityToken helper**

Add to the service's public API (either as a method on the service object or as an exported function):

```typescript
async issueCapabilityToken(
  principal: string,
  capability: string,
  scope: string[],
  opts?: {
    purposeParameters?: Record<string, unknown>;
    ttlHours?: number;
    budget?: Budget;
  }
): Promise<TokenResponse> {
  // Root issuance only. scope must be explicitly provided —
  // capability names and scope strings are different things.
  // For delegation flows, use issueToken() directly.
  return this.issueToken(principal, {
    subject: principal,
    capability,
    scope,
    ttl_hours: opts?.ttlHours ?? 2,
    purpose_parameters: opts?.purposeParameters,
    budget: opts?.budget,
  });
}
```

- [ ] **Step 2: Add tests**

Add test verifying `issueCapabilityToken` produces a token bound to the capability.

- [ ] **Step 3: Run tests**

Run: `cd /Users/samirski/Development/ANIP/packages/typescript && npm test 2>&1 | tail -20`

- [ ] **Step 4: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(typescript): add issueCapabilityToken helper"
```

---

## Task 3: Go — Document Sync-Only Auth + Add IssueCapabilityToken

Go's auth hook is sync-only by design (function signature). Needs documentation and the helper.

**Files:**
- Modify: `packages/go/service/service.go`

- [ ] **Step 1: Add doc comment to auth hook field**

In `service.go`, update the `Authenticate` field comment in the `Config` struct:

```go
// Authenticate is called to verify a bearer token and return the principal.
// This hook is synchronous — it is called directly in the request path.
// If your authentication requires I/O, perform it before registering the hook
// or use a caching wrapper.
Authenticate func(bearer string) (principal string, ok bool)
```

- [ ] **Step 2: Add IssueCapabilityToken helper**

Add to `Service`:

```go
// IssueCapabilityToken issues a root token pre-bound to a specific capability.
// scope must be explicitly provided — capability names and scope strings
// are different things.
// For delegation flows (parent_token, subject), use IssueToken directly.
func (s *Service) IssueCapabilityToken(principal, capability string, scope []string, opts ...TokenOption) (core.TokenResponse, error) {
    req := core.TokenRequest{
        Subject:    principal,
        Capability: capability,
        Scope:      scope,
        TTLHours:   2,
    }
    for _, opt := range opts {
        opt(&req)
    }
    return s.IssueToken(principal, req)
}
```

Also add `TokenOption` type if it doesn't exist:
```go
type TokenOption func(*core.TokenRequest)

func WithTTL(hours int) TokenOption {
    return func(r *core.TokenRequest) { r.TTLHours = hours }
}

func WithBudget(budget *core.Budget) TokenOption {
    return func(r *core.TokenRequest) { r.Budget = budget }
}

func WithPurposeParameters(params map[string]interface{}) TokenOption {
    return func(r *core.TokenRequest) { r.PurposeParameters = params }
}
```

- [ ] **Step 3: Add tests**

Add test for `IssueCapabilityToken` in `service_test.go`.

- [ ] **Step 4: Run tests**

Run: `cd /Users/samirski/Development/ANIP/packages/go && go test ./... 2>&1 | tail -20`

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/
git commit -m "feat(go): document sync-only auth + add IssueCapabilityToken helper"
```

---

## Task 4: Java — Document Sync-Only Auth + Add issueCapabilityToken

**Files:**
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java`

- [ ] **Step 1: Add Javadoc to auth hook field**

Update the `authenticate` field documentation:

```java
/**
 * Bootstrap authentication hook. Called synchronously in the request path
 * to verify a bearer token and return the principal identity.
 * <p>
 * This hook is intentionally synchronous. If your authentication requires
 * asynchronous I/O, perform it before registering the hook or use a caching wrapper.
 */
private final Function<String, Optional<String>> authenticate;
```

- [ ] **Step 2: Add issueCapabilityToken helper**

Add to `ANIPService`:

```java
/**
 * Issue a root token pre-bound to a specific capability.
 * scope must be explicitly provided — capability names and scope strings
 * are different things.
 * For delegation flows (parentToken, subject), use issueToken() directly.
 */
public TokenResponse issueCapabilityToken(
        String principal,
        String capability,
        List<String> scope,
        Map<String, Object> purposeParameters,
        int ttlHours,
        Budget budget) {
    TokenRequest request = new TokenRequest(
            principal, scope, capability, purposeParameters,
            null, ttlHours, null, budget);
    return issueToken(principal, request);
}

// Overload with defaults
public TokenResponse issueCapabilityToken(String principal, String capability, List<String> scope) {
    return issueCapabilityToken(principal, capability, scope, null, 2, null);
}
```

- [ ] **Step 3: Add tests**

- [ ] **Step 4: Run tests**

Run: `cd /Users/samirski/Development/ANIP/packages/java && mvn test 2>&1 | tail -20`

- [ ] **Step 5: Commit**

```bash
git add packages/java/anip-service/
git commit -m "feat(java): document sync-only auth + add issueCapabilityToken helper"
```

---

## Task 5: C# — Document Sync-Only Auth + Add IssueCapabilityToken

**Files:**
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs`

- [ ] **Step 1: Add XML doc to auth hook field**

```csharp
/// <summary>
/// Bootstrap authentication hook. Called synchronously in the request path
/// to verify a bearer token and return the principal identity.
/// This hook is intentionally synchronous. If your authentication requires
/// async I/O, perform it before registering the hook or use a caching wrapper.
/// </summary>
private readonly Func<string, string?>? _authenticate;
```

- [ ] **Step 2: Add IssueCapabilityToken helper**

```csharp
/// <summary>
/// Issue a root token pre-bound to a specific capability.
/// For delegation flows (parentToken, subject), use IssueToken() directly.
/// </summary>
/// <remarks>
/// scope must be explicitly provided — capability names and scope strings
/// are different things.
/// </remarks>
public TokenResponse IssueCapabilityToken(
    string principal,
    string capability,
    string[] scope,
    Dictionary<string, object>? purposeParameters = null,
    int ttlHours = 2,
    Budget? budget = null)
{
    var request = new TokenRequest
    {
        Subject = principal,
        Capability = capability,
        Scope = scope,
        PurposeParameters = purposeParameters,
        TtlHours = ttlHours,
        Budget = budget,
    };
    return IssueToken(principal, request);
}
```

- [ ] **Step 3: Add tests**

- [ ] **Step 4: Run tests**

Run: `cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test 2>&1 | tail -20`

- [ ] **Step 5: Commit**

```bash
git add packages/csharp/src/Anip.Service/ packages/csharp/test/
git commit -m "feat(csharp): document sync-only auth + add IssueCapabilityToken helper"
```

---

## Task 6: Update Example Apps

Update example apps to demonstrate the new `issueCapabilityToken` helpers where they currently construct token requests with `capability` manually.

**Files:**
- Check: `examples/` directory for token issuance patterns

- [ ] **Step 1: Find example apps that issue tokens**

Search for manual token request construction in example apps (target issuance patterns, not capability declarations):
```bash
grep -rn "issueToken\|issue_token\|IssueToken\|TokenRequest" examples/ --include="*.py" --include="*.ts" --include="*.go" --include="*.java" --include="*.cs"
```

- [ ] **Step 2: Update relevant examples to use issueCapabilityToken**

Where example apps manually construct `{capability: "...", scope: [...]}` in token requests, replace with the new helper to demonstrate the recommended pattern.

- [ ] **Step 3: Run conformance tests**

Run conformance tests for all runtimes to verify nothing broke.

- [ ] **Step 4: Commit**

Stage only the files that actually changed:
```bash
git add examples/<changed-files>
git commit -m "docs(examples): use issueCapabilityToken helpers in example apps"
```

