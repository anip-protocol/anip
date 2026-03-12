# Sequence Diagrams Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 5 Mermaid sequence diagrams to ANIP documentation — README, SPEC, trust model doc, and adapter READMEs.

**Architecture:** Each diagram is a fenced Mermaid `sequenceDiagram` block inserted at a specific location in an existing markdown file. No code changes — documentation only. Each task adds one diagram to all its target files.

**Tech Stack:** Mermaid markdown (GitHub-rendered)

**Design doc:** `docs/plans/2026-03-12-sequence-diagrams-design.md`

---

### Task 1: Native ANIP Invoke Flow — README + SPEC

**Files:**
- Modify: `README.md` — insert after line 69 ("Decides to proceed, executes with full context" closing ```)
- Modify: `SPEC.md` — add after the numbered list at lines 713-721 (section 6.4 "Agent Interaction Flow")

**Step 1: Add diagram to README.md**

Insert the following after the "With ANIP:" code block (after line 69, before "Every assumption that was implicit..."):

```markdown

```mermaid
sequenceDiagram
    participant Agent
    participant ANIP as ANIP Service

    Agent->>ANIP: GET /.well-known/anip
    ANIP-->>Agent: discovery (capabilities, endpoints)

    Agent->>ANIP: GET /anip/manifest
    ANIP-->>Agent: full capability declarations

    Agent->>ANIP: POST /anip/tokens (+ API key)
    ANIP-->>Agent: signed JWT delegation token

    Agent->>ANIP: POST /anip/invoke/search_flights (+ token)
    ANIP-->>Agent: {success, result, cost_actual}
`` `
```

(Remove the space in the closing fence above — it's there to avoid breaking this plan's markdown.)

**Step 2: Add diagram to SPEC.md**

In section 6.4 "Agent Interaction Flow", keep the existing numbered list but add the Mermaid diagram after it (after line 721, before line 723 "Not every interaction requires all steps"):

Same diagram as Step 1.

**Step 3: Verify rendering**

Open both files on GitHub (or use a local Mermaid previewer) to confirm the diagrams render correctly.

**Step 4: Commit**

```bash
git add README.md SPEC.md
git commit -m "docs: add native ANIP invoke flow sequence diagram"
```

---

### Task 2: Budget Escalation Flow — README + SPEC

**Files:**
- Modify: `README.md` — insert after the "Five things" list (after line 80, before "See it in action")
- Modify: `SPEC.md` — insert in section 4.5 "Failure Semantics" or after the invoke flow in section 6.4

**Step 1: Add diagram to README.md**

Insert after line 80 ("That's a capability that doesn't exist in REST, MCP, or OpenAPI."):

```markdown

```mermaid
sequenceDiagram
    participant Agent
    participant ANIP as ANIP Service
    participant Human

    Agent->>ANIP: POST /anip/invoke/book_flight (+ token)
    ANIP-->>Agent: budget_exceeded (grantable_by: human)

    Agent->>Human: request_budget_increase ($380, UA205)
    Human-->>Agent: approved

    Human->>ANIP: POST /anip/tokens (higher budget)
    ANIP-->>Human: new signed JWT

    Human-->>Agent: new token

    Agent->>ANIP: POST /anip/invoke/book_flight (+ new token)
    ANIP-->>Agent: {success: true, booking: BK-0018}
`` `
```

**Step 2: Add diagram to SPEC.md**

Insert the same diagram in section 6.4, after the native invoke flow diagram from Task 1. Add a brief heading:

```markdown
#### Budget Escalation

When a capability invocation fails due to insufficient budget, the structured failure includes `resolution.grantable_by`, enabling the agent to escalate autonomously:
```

Followed by the same Mermaid diagram.

**Step 3: Commit**

```bash
git add README.md SPEC.md
git commit -m "docs: add budget escalation sequence diagram"
```

---

### Task 3: v0.2 Signed Trust Flow — SPEC + trust-model-v0.2.md

**Files:**
- Modify: `SPEC.md` — insert in section 7 "Trust Model", after the v2 verification mechanisms list
- Modify: `docs/trust-model-v0.2.md` — replace or augment the ASCII diagram at lines 42-57 (section 2 "Issuance Flow")

**Step 1: Add diagram to trust-model-v0.2.md**

Replace the existing ASCII diagram in section 2 "Issuance Flow" (lines 42-57) with a Mermaid sequence diagram:

```markdown

```mermaid
sequenceDiagram
    participant Caller
    participant ANIP as ANIP Service

    Caller->>ANIP: GET /.well-known/anip
    ANIP-->>Caller: discovery + JWKS URL

    Caller->>ANIP: GET /.well-known/jwks.json
    ANIP-->>Caller: public keys (ES256)

    Caller->>ANIP: GET /anip/manifest
    ANIP-->>Caller: manifest + detached JWS signature

    Note over Caller: verify manifest signature with JWKS

    Caller->>ANIP: POST /anip/tokens (Authorization: Bearer <key>)
    ANIP-->>Caller: {issued: true, token: <signed JWT>}

    Caller->>ANIP: POST /anip/invoke/capability (+ JWT)
    Note over ANIP: verify JWT signature, check claims vs stored token
    ANIP-->>Caller: {success, result, cost_actual}
`` `
```

Keep the prose paragraph after the diagram ("The service is the sole token issuer...").

**Step 2: Add diagram to SPEC.md**

Insert in section 7 "Trust Model", immediately after the "Path to Verification (v2+)" heading and its introductory list of solution space items (after line 744, before the contract testing schema). This places the diagram right where the reader transitions from "what v2 adds" to the details. Add a brief intro:

```markdown
### v0.2 Trust Flow

The v0.2 reference implementation realizes signed manifests and signed delegation tokens:
```

Followed by the same Mermaid diagram.

**Step 3: Commit**

```bash
git add SPEC.md docs/trust-model-v0.2.md
git commit -m "docs: add v0.2 signed trust flow sequence diagram"
```

---

### Task 4: MCP Adapter Flow + README Prose Refresh — mcp-py + mcp-ts

The MCP adapter READMEs still describe v0.1 behavior (root token registration, adapter-constructed tokens, configured issuer). The code was migrated to v0.2 but the READMEs were not updated. This task adds the diagram AND refreshes stale prose to match the current v0.2 signed-token behavior.

**Files:**
- Modify: `adapters/mcp-py/README.md` — prose refresh + diagram insertion
- Modify: `adapters/mcp-ts/README.md` — prose refresh + diagram insertion

**Step 1: Update mcp-py/README.md prose**

The following sections contain stale v0.1 references and need updating:

a) **Configuration section (lines 54-79):** Remove `delegation:` block from example YAML (issuer, scope, token_ttl_minutes). Replace with v0.2 config showing `api_key` and `scope`. Remove `ANIP_ISSUER` env var reference.

b) **Delegation Configuration section (lines 81-89):** Rewrite entirely. The adapter no longer "creates delegation tokens on behalf of the configured issuer." It requests signed tokens from the ANIP service using an API key. Each tool invocation gets a per-capability token issued by the server, not constructed by the adapter.

c) **How It Works section (lines 91-98):** Update steps:
- Step 3: change "registers a root delegation token" → "no root token needed (v0.2 issues per-request tokens)"
- Step 5: change "creates a purpose-bound token" → "requests a signed capability token from the ANIP service (using API key)"

d) **Key Design Decisions section (lines 152-160):**
- "Per-invocation tokens" paragraph: change "Each tool call creates a fresh delegation token" → "Each tool call requests a fresh signed token from the ANIP service." Change "token registration + capability invocation" → "token request + capability invocation."

e) **Limitations section (lines 162-167):**
- "Single identity" bullet: update to reflect that the adapter uses a configured API key (not a configured issuer). All invocations share the same API key identity.

f) **Translation Loss table (line 126):** Update "Delegation Chain" row from "adapter holds a single identity, per-tool scope narrowing" → "adapter uses a single API key, per-tool scope narrowing via server-issued tokens"

g) **Architecture file descriptions (line 145):** Change `invocation.py` description from "Delegation token management + ANIP invocation" → "Token request + ANIP invocation"

**Step 2: Add diagram to mcp-py/README.md**

Insert after the updated "How It Works" numbered list, before "### Description Enrichment":

```markdown

```mermaid
sequenceDiagram
    participant MCP as MCP Host
    participant Adapter as MCP Adapter
    participant ANIP as ANIP Service

    Note over Adapter,ANIP: Startup
    Adapter->>ANIP: GET /.well-known/anip
    ANIP-->>Adapter: discovery
    Adapter->>ANIP: GET /anip/manifest
    ANIP-->>Adapter: capabilities
    Note over Adapter: generate MCP tools from capabilities

    Note over MCP,ANIP: Tool Invocation
    MCP->>Adapter: tool call (search_flights, args)
    Adapter->>ANIP: POST /anip/tokens (+ API key, scoped)
    ANIP-->>Adapter: signed JWT
    Adapter->>ANIP: POST /anip/invoke/search_flights (+ JWT)
    ANIP-->>Adapter: {success, result, cost_actual}
    Adapter-->>MCP: MCP tool result (text)
`` `
```

**Step 3: Update mcp-ts/README.md**

a) Update Architecture file descriptions: `invocation.ts` from "Delegation token management + ANIP invocation" → "Token request + ANIP invocation"

b) Insert the same diagram after the Architecture section.

**Step 4: Commit**

```bash
git add adapters/mcp-py/README.md adapters/mcp-ts/README.md
git commit -m "docs: refresh MCP adapter READMEs for v0.2 + add flow diagram"
```

---

### Task 5: REST/GraphQL Adapter Flow — 4 adapter READMEs

**Files:**
- Modify: `adapters/rest-py/README.md` — insert in the "Authentication" section
- Modify: `adapters/rest-ts/README.md` — same
- Modify: `adapters/graphql-py/README.md` — same
- Modify: `adapters/graphql-ts/README.md` — same

**Step 1: Create the diagram**

All four adapters get the same diagram, inserted after the Authentication section's header table (after "If neither header is provided, the adapter returns 401." for REST or the equivalent for GraphQL):

For REST adapters:

```markdown

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant Adapter as REST Adapter
    participant ANIP as ANIP Service

    rect rgb(230, 245, 230)
    Note over Client,ANIP: Preferred: Signed Token Path
    Client->>Adapter: GET /api/search_flights (X-ANIP-Token: <JWT>)
    Adapter->>ANIP: POST /anip/invoke/search_flights (+ JWT)
    ANIP-->>Adapter: {success, result}
    Adapter-->>Client: 200 {success, result}
    end

    rect rgb(255, 243, 224)
    Note over Client,ANIP: Convenience: API Key Path
    Client->>Adapter: GET /api/search_flights (X-ANIP-API-Key: <key>)
    Adapter->>ANIP: POST /anip/tokens (+ key, scoped)
    ANIP-->>Adapter: signed JWT
    Adapter->>ANIP: POST /anip/invoke/search_flights (+ JWT)
    ANIP-->>Adapter: {success, result}
    Adapter-->>Client: 200 {success, result}
    Note over Adapter: audit subject = adapter identity, not caller
    end
`` `
```

For GraphQL adapters, use the same diagram but change:
- participant name: `Adapter as GraphQL Adapter`
- request: `POST /graphql (X-ANIP-Token: <JWT>)` and `POST /graphql (X-ANIP-API-Key: <key>)`
- response: `200 {data: {searchFlights: ...}}`

**Step 2: Insert into all 4 READMEs**

Insert after the credential precedence explanation in the Authentication section of each file.

**Step 3: Commit**

```bash
git add adapters/rest-py/README.md adapters/rest-ts/README.md adapters/graphql-py/README.md adapters/graphql-ts/README.md
git commit -m "docs: add REST/GraphQL adapter credential flow sequence diagram"
```
