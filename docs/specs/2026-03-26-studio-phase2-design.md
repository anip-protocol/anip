# ANIP Studio Phase 2: Invocation — Design Spec

## Purpose

Phase 2 adds interactive capability invocation to ANIP Studio. Phase 1 made services inspectable (discovery, manifest, JWKS, audit, checkpoints). Phase 2 makes them usable — invoke capabilities, inspect permissions, and see structured success/failure responses.

## Scope

**Phase 2 v1 includes:**

1. **Invoke view** — form-based capability invocation with unary request/response
2. **Permissions panel** — auto-check via `POST /anip/permissions` when token or capability changes
3. **Structured failure display** — success/failure rendering with real ANIP failure structure and recovery fields

**Phase 2 v1 does not include:**

- Streaming visualization (Phase 2.1 — POST with auth/body over SSE is non-trivial)
- Lineage visualization (later — identifiers are surfaced in results but no dedicated trace view)
- Workflow editor, multi-step invocation, or cross-service orchestration

If a capability declares streaming in `response_modes`, the invoke view shows: "Streaming supported; Studio currently invokes in unary mode."

## Architecture

### What changes

- New route: `/invoke/:capability?`
- New nav item in sidebar: "Invoke"
- New components: `InvokeView.vue`, `InvokeForm.vue`, `PermissionsPanel.vue`, `InvokeResult.vue`
- New API functions in `api.ts`: `invokeCapability`, `fetchPermissions`
- Small addition to `CapabilityCard.vue`: `<router-link>` to `/invoke/:name`

### What doesn't change

- Phase 1 views remain read-only (Discovery, Manifest, JWKS, Audit, Checkpoints)
- `store.ts` — no new global state. The invoke view manages its own local state. `store.bearer` (already global) is reused.
- No new dependencies. Same Vue 3 + Vite + vue-router stack.

## Route

```
/invoke/:capability?
```

- If `:capability` is provided (deep link from Manifest), auto-selects that capability and loads its declaration.
- If omitted, shows a capability picker dropdown populated from `Object.keys(manifest.capabilities)`. Each option shows the capability name and its side-effect type badge.

Manifest's `CapabilityCard` gets a `<router-link :to="'/invoke/' + name">` — a small secondary "Invoke" link in the card header. This bridges Phase 1 inspection to Phase 2 interaction without cluttering the Manifest view.

## Invoke View Layout

Single-column stacked layout. Top to bottom:

### 1. Declaration Summary Bar

Capability name, side-effect type badge, required scope chips, cost declaration summary (if any). If the capability declares streaming: "Streaming supported; Studio currently invokes in unary mode."

When no capability is selected, shows the dropdown picker instead.

### 2. Auth Bar

Reuses the existing `BearerInput` component. The token in `store.bearer` is shared across all views — entering a token on the invoke page makes it available in Audit and other views that need it.

### 3. Permissions Panel

Calls `POST /anip/permissions` to show what the current token allows.

**Permissions are advisory, not authoritative.** The actual invocation result remains the source of truth. Token context or server state may change between the permissions check and the invocation. The panel is a pre-flight signal, not a guarantee.

**Auto-triggers** when `bearer` or selected capability changes (and both are present).

**Five display states:**

The ANIP permissions response returns three buckets: `available`, `restricted`, and `denied`. These map to distinct UI states because the distinction is meaningful — restricted means a missing but grantable scope, denied means something ungrantable (e.g., requires admin principal).

| State | Indicator | Content |
|-------|-----------|---------|
| No token | Neutral | "Enter a bearer token to inspect permissions" |
| Available | Green dot | "Available" + granted scopes |
| Restricted | Amber dot | "Restricted" + missing scopes (grantable) |
| Denied | Red dot | "Denied" + reason (ungrantable — e.g., wrong caller class) |
| Error/unknown | Grey dot | "Unable to check permissions" + error message |

"Restricted" means the server understood the request and the token lacks a grantable scope. "Denied" means the capability is not accessible to this caller regardless of scope (e.g., requires a different principal class). "Error/unknown" covers transport failures, malformed responses, and unexpected errors — distinct from both restricted and denied.

A small "Refresh" link is always visible when a result is showing.

### 4. Input Form

Generated from the manifest's `inputs` array for the selected capability.

Each field renders as:
- Label: field name (monospace), type, required indicator (`*`)
- Text input
- Default value pre-filled from `inputs[].default` if present

All inputs are submitted as strings. No client-side type coercion in v1. The server is the source of truth for validation and parsing.

User edits are preserved in a map (`capability → inputs`) so switching between capabilities and back doesn't lose work.

### 5. Invoke Button

Label: "Invoke {capability_name}". Disabled when: no bearer token, no capability selected, or required fields empty.

### 6. Result Panel

Hidden until first invocation. Renders based on `result.success`:

**Success rendering:**
- Green "Success" badge
- `invocation_id` — prominent, monospace
- `client_reference_id` — if present
- `cost_actual` — if present (currency + amount)
- Result data in collapsible JSON panel

**Failure rendering:**

The invocation response nests failure details inside a `failure` object:

```json
{
  "success": false,
  "failure": {
    "type": "budget_exceeded",
    "detail": "Requested booking costs $487.00...",
    "retry": false,
    "resolution": {
      "action": "request_budget_increase",
      "requires": "higher_budget",
      "grantable_by": "delegating_principal",
      "estimated_availability": "immediate"
    }
  },
  "invocation_id": "...",
  "client_reference_id": "..."
}
```

Rendered as:
- Red "Failed" badge + amber `failure.type` badge
- `failure.detail` — human-readable text
- Resolution fields (from `failure.resolution`, rendered as accent-bordered callout):
  - `failure.resolution.action` — what to do
  - `failure.resolution.requires` — what's needed
  - `failure.resolution.grantable_by` — who can grant it
  - `failure.resolution.estimated_availability` — if present
- `failure.retry` — boolean, shown as "Retryable: yes/no"
- `invocation_id` — prominent, monospace (same position as success)
- `client_reference_id` — if present
- Collapsible "Show raw response" toggle for the full JSON

## Component Contracts

### `InvokeForm.vue`

Dumb form component. Declaration in, values and events out.

- **Props:** `declaration` (capability object from manifest), `initialValues` (optional `Record<string, string>` for preserved edits)
- **Emits:** `submit(inputs: Record<string, string>)`, `update(inputs: Record<string, string>)`
- Renders input fields from `declaration.inputs[]`
- No validation beyond disabling submit when required fields are empty

### `PermissionsPanel.vue`

Auto-check permissions display.

- **Props:** `bearer`, `capability` (nullable string)
- **Internal state:** `loading`, `result`, `error`
- Uses `store.baseUrl` directly (consistent with Phase 1 views like `AuditView`)
- **Watches** `bearer` and `capability` — when either changes (and both are present), calls `fetchPermissions`
- The `capability` prop may be used for local filtering/presentation even if `POST /anip/permissions` doesn't support filtering by capability server-side. The API wrapper is honest about what it actually sends to the server.
- Renders the five display states described above (no token, available, restricted, denied, error)

### `InvokeResult.vue`

Result rendering for success and failure.

- **Props:** `result` (full invocation response object, nullable)
- When `result` is null: hidden
- When `result.success` is true: success rendering
- When `result.success` is false: failure rendering with structured ANIP fields

### `InvokeView.vue`

Orchestrator. Manages the page lifecycle.

- Fetches manifest on mount (reuses `fetchManifest` from `api.ts`). Follows the same loading/error/retry pattern as `ManifestView` — loading spinner, error text with retry button.
- Reads `:capability` from route params, or shows dropdown picker
- Local state: `selectedCapability`, `userInputs` (map of `capability → Record<string, string>`), `invokeResult`, `invoking` (boolean)
- On capability change from route param: reset selected capability and result, keep preserved inputs map
- Passes props to child components, handles `submit` from `InvokeForm`
- On invoke: sets `invoking = true`, calls `invokeCapability`, stores result, sets `invoking = false`

## API Layer

Two new functions in `api.ts`:

```typescript
export async function invokeCapability(
  baseUrl: string,
  bearer: string,
  capability: string,
  inputs: Record<string, any>,
): Promise<any> {
  // POST /anip/invoke/{capability}
  // Authorization: Bearer {bearer}
  // Body: { parameters: inputs }
}

export async function fetchPermissions(
  baseUrl: string,
  bearer: string,
  capability?: string,
): Promise<any> {
  // POST /anip/permissions
  // Authorization: Bearer {bearer}
  // Body: { capability } if supported, {} otherwise
}
```

**Error handling distinction:**

- `invokeCapability` does NOT throw on non-2xx responses that contain a valid ANIP failure body (`{ success: false, failure: { ... } }`). It parses the response JSON regardless of HTTP status and returns the structured object. This is critical — the ANIP HTTP binding returns invocation failures as non-2xx JSON bodies, and `InvokeResult` needs the full `{ success, failure, invocation_id }` payload to render structured failure UX. `invokeCapability` only throws on actual transport errors (network failure, non-JSON response, malformed body).
- `fetchPermissions` throws on non-OK responses. The `PermissionsPanel` catches errors and renders them as the "Error/unknown" state.

## Navigation

Add "Invoke" to the sidebar nav in `App.vue`:

```typescript
{ name: 'invoke', label: 'Invoke', icon: '\u{26A1}', path: '/invoke' },
```

The route definition in `router.ts` uses `name: 'invoke'` (consistent with the existing pattern where each route has a name).

Position: after Checkpoints (last in the Phase 1 list). This keeps Phase 1 inspection items grouped, with the Phase 2 interactive item below.

## What This Does Not Cover

- Streaming visualization — Phase 2.1
- Lineage tracing view — later (identifiers are surfaced in results)
- Token issuance from Studio — use the CLI or API directly
- Client-side input validation beyond required-field checks
- Cost range validation against declared ranges
- Capability comparison or diffing
