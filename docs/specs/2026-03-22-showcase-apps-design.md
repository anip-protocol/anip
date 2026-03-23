# ANIP Showcase Apps Design

## Purpose

Three standalone Python applications that demonstrate ANIP's full protocol surface in realistic scenarios. Each app is self-contained, runs independently, and exercises a distinct subset of ANIP features. Together they prove that ANIP handles accessible consumer workflows, high-stakes governance, and technical operations.

These are not minimal starters (that's `examples/anip/`). These are richer demonstrations that show why ANIP exists and what it enables.

## Scenario Portfolio

### 1. Travel Booking (`examples/showcase/travel/`)

**Role:** Accessible introductory scenario. Shows the core ANIP value without policy complexity.

**Capabilities:**
- `search_flights` — read, streaming declared (unary invocation in demo)
- `check_availability` — read
- `book_flight` — irreversible, cost: financial (estimated range), requires: `search_flights`
- `cancel_booking` — transactional, rollback_window: "PT24H"

**ANIP features exercised:**
- Cost estimation vs cost actual (search estimates, booking confirms)
- Scope enforcement (search-only token blocked from booking, with structured resolution)
- Scope narrowing (broad parent token → narrowed search-only and booking-only child tokens)
- Capability prerequisites (`book_flight` requires prior `search_flights`)
- Permission discovery (agent checks what it can do before acting)
- Audit trail (full invocation history with event classification)
- Streaming declaration (`search_flights` declares streaming support)
- Side-effect typing (read vs irreversible vs transactional)

**Delegation model:** Simple — human → agent. Broad parent token narrowed to child tokens. No sub-agent chains.

**Demo script (`demo.py`):** An agent searches flights, attempts booking with a search-only token (scope enforcement), gets a new booking-scoped token (simulated human approval), books, and verifies the audit trail.

---

### 2. Financial Operations (`examples/showcase/finance/`)

**Role:** Strongest governance/compliance scenario. Makes the ANIP value proposition sharp — trial-and-error is unacceptable here.

**Capabilities:**
- `query_portfolio` — read
- `get_market_data` — read, streaming declared (unary invocation in demo)
- `execute_trade` — irreversible, cost: financial (fixed per trade), requires: `get_market_data`
- `transfer_funds` — transactional, rollback_window: "PT1H", cost: financial (fixed fee)
- `generate_report` — write

**ANIP features exercised (centerpieces):**
- **Disclosure policy** (centerpiece) — same scope_insufficient failure rendered three different ways based on caller_class:
  - `internal` class → full disclosure (type, detail, resolution with grantable_by)
  - `partner` class → reduced disclosure (detail truncated, grantable_by hidden)
  - `default` class → redacted disclosure (generic messages only)
- **Retention tiers** — audit entries classified by event_class with tiered retention (long/medium/short/aggregate_only)
- **Anchored trust** — checkpoint scheduling every 30s (may require ~30s for first checkpoint to appear)
- **Multi-hop delegation narrowing** — compliance officer → trader ($50K) → execution agent ($10K). Child cannot widen parent scope or budget.
- **Cost signaling** — trade cost estimated via `get_market_data`, confirmed via `cost_actual`

**Demo script (`demo.py`):** A compliance officer delegates to a trader, who sub-delegates to an execution agent. The agent queries portfolio, checks market data, executes a trade with cost tracking. Then the disclosure policy centerpiece: the same scope failure is shown at full, reduced, and redacted levels based on caller_class. Audit entries show event classification and retention tiers.

---

### 3. DevOps / Infrastructure (`examples/showcase/devops/`)

**Role:** Most relatable technical/operator scenario. Helps engineers see ANIP outside consumer flows.

**Capabilities:**
- `list_deployments` — read
- `get_service_health` — read
- `scale_replicas` — write
- `update_config` — write
- `rollback_deployment` — transactional, rollback_window: "PT2H" (can roll forward again within window)
- `delete_resource` — irreversible

**ANIP features exercised (centerpieces):**
- **Scope-bound rollback token** (centerpiece) — rollback-only token via `infra.deploy` scope. Purpose parameters (reason, target_service) carried as metadata but not enforced by the handler — scope is what restricts the token.
- **Side-effect typing** — all four types represented (read, write, transactional, irreversible)
- **Health endpoint** — enabled, integrated with the service's own operational story
- **Repeated-denial aggregation** — three consecutive delete attempts denied; with `aggregation_window=60`, these will be aggregated after the window closes (~60s). Demo audit step may show individual entries if queried before flush.
- **Scoped delegation** — platform-team → app-team → CI agent, each with narrower scope
- **Observability hooks** — logging hooks fire on every invocation, demonstrating the hook system

**Demo script (`demo.py`):** A platform engineer delegates deployment authority to an app team, who delegates to a CI agent. The CI agent lists deployments, checks health, scales replicas, then a scope-bound rollback token is demonstrated (can rollback, blocked from scaling and deleting). Three delete attempts show scope enforcement with structured resolution. Audit entries show event classification.

---

## Architecture

### Stack

All three apps use the same Python stack:
- `anip-service` + `anip-fastapi` for the core ANIP protocol
- `anip-rest` for REST/OpenAPI interface
- `anip-graphql` for GraphQL interface
- `anip-mcp` for MCP Streamable HTTP interface (mounted on FastAPI)

Each app mounts all four HTTP surfaces (ANIP protocol + REST + GraphQL + MCP Streamable HTTP) on a single FastAPI service. MCP stdio is a separate integration mode (not mounted on the web server) and is not part of the showcase app demos.

### Storage

- Default: in-memory (`:memory:`)
- Configurable via `ANIP_STORAGE` env var
- SQLite (`sqlite:///showcase.db`) as the first non-memory path for persistent audit/checkpoint demos
- PostgreSQL supported but not required for the showcase

### Structure per app

```
examples/showcase/{scenario}/
├── README.md           # What this app demonstrates, how to run it
├── app.py              # FastAPI application with ANIP + adapters
├── capabilities.py     # Capability declarations and handlers
├── data.py             # Static/mock domain data
├── demo.py             # Scripted agent interaction flow
└── requirements.txt    # Python deps (or pyproject.toml)
```

### Self-contained

No shared code between the three apps. Each is fully independent. If patterns emerge later, extraction can happen then.

### Configuration

Each app uses environment variables for configuration:
- `ANIP_STORAGE` — storage DSN (default: `:memory:`)
- `ANIP_TRUST_LEVEL` — trust level (default: `signed`, finance uses `anchored`)
- `ANIP_KEY_PATH` — key directory (default: `./anip-keys`)
- `PORT` — HTTP port (default: `8000`)

## Build Order

1. **Travel** first — extends the familiar flight domain, validates the showcase app structure
2. **Finance** second — most complex, exercises governance features
3. **DevOps** third — operator-focused, exercises observability and aggregation

Each app should be buildable and demoable independently. No dependency on the others.

## What This Is Not

- Not a multi-service orchestration demo (that requires federated trust, which isn't in the spec yet)
- Not a production application (mock data, simplified domain logic)
- Not a language portability proof (Python only — runtime parity is already proven by 5 conformance-passing runtimes)
- Not a UI (the demo scripts are CLI agent flows, not web interfaces)

## Success Criteria

Each showcase app should:
1. Start with `python app.py` (or `uvicorn`)
2. Pass the conformance suite
3. Have a `demo.py` that runs a complete agent interaction flow end-to-end
4. Demonstrate its designated ANIP features visibly in the demo output
5. Have a README that explains what ANIP features it demonstrates and why they matter in this domain
