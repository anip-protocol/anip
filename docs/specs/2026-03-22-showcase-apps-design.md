# ANIP Showcase Apps Design

## Purpose

Three standalone Python applications that demonstrate ANIP's full protocol surface in realistic scenarios. Each app is self-contained, runs independently, and exercises a distinct subset of ANIP features. Together they prove that ANIP handles accessible consumer workflows, high-stakes governance, and technical operations.

These are not minimal starters (that's `examples/anip/`). These are richer demonstrations that show why ANIP exists and what it enables.

## Scenario Portfolio

### 1. Travel Booking (`examples/showcase/travel/`)

**Role:** Accessible introductory scenario. Shows the core ANIP value without policy complexity.

**Capabilities:**
- `search_flights` — read, streaming (progressive results via SSE)
- `check_availability` — read
- `book_flight` — irreversible, cost: financial (estimated range), requires: `search_flights`
- `cancel_booking` — transactional, rollback_window: "PT24H"

**ANIP features exercised:**
- Cost estimation vs cost actual (search estimates, booking confirms)
- Budget enforcement (agent has a $500 budget, nonstop flights exceed it)
- Scope narrowing (full travel scope → booking-only token)
- Capability prerequisites (`book_flight` requires prior `search_flights`)
- Permission discovery (agent checks what it can do before acting)
- Audit trail (full invocation history)
- Streaming (search results arrive progressively)
- Side-effect typing (read vs irreversible vs transactional)

**Delegation model:** Simple — human → agent. One bounded delegated booking token. No sub-agent chains.

**Demo script (`demo.py`):** An agent searches flights, hits the budget wall, requests budget increase (simulated human approval), books, and verifies the audit trail. Same flow as the existing `examples/agent/` demo but richer.

---

### 2. Financial Operations (`examples/showcase/finance/`)

**Role:** Strongest governance/compliance scenario. Makes the ANIP value proposition sharp — trial-and-error is unacceptable here.

**Capabilities:**
- `query_portfolio` — read
- `get_market_data` — read, streaming (live price updates via SSE)
- `execute_trade` — irreversible, cost: financial (fixed per trade), requires: `get_market_data`
- `transfer_funds` — transactional, rollback_window: "PT1H", cost: financial (fixed fee)
- `generate_report` — write

**ANIP features exercised (centerpieces):**
- **Disclosure policy** — this is the main place to show caller-class-aware failure detail:
  - `internal` class → full disclosure (type, detail, resolution with grantable_by)
  - `partner` class → reduced disclosure (detail truncated, grantable_by hidden)
  - `default` class → redacted disclosure (generic messages only)
- **Retention tiers** — trades and transfers on long retention (P365D), queries on short (P7D), denied attempts on medium (P90D)
- **Checkpoint proofs** — anchored trust level, automatic checkpoint scheduling, inclusion proof verification
- **Strict delegation narrowing** — compliance officer → trader ($50K budget) → execution agent ($10K sub-budget). Child cannot widen parent scope or budget.
- **Multi-hop delegation chain** — three levels of authority, each narrower
- **Cost signaling with variance tracking** — declared estimate vs actual, logged in audit

**Demo script (`demo.py`):** A compliance officer delegates to a trader agent, who sub-delegates to an execution agent. The execution agent queries the portfolio, checks market data (streaming), attempts a trade that exceeds its budget (denied with full resolution for internal callers), gets the budget increased, executes, and the compliance officer verifies the audit trail with checkpoint proof.

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
- **Purpose-bound tokens** — rollback token scoped to incident response only, not general deployment
- **Side-effect typing** — all four types represented (read, write, transactional, irreversible)
- **Health endpoint** — enabled, integrated with the service's own operational story
- **Repeated-denial aggregation** — a CI agent repeatedly tries to scale beyond its scope, aggregated into a single audit entry
- **Scoped delegation** — platform-team → app-team → CI agent, each with narrower scope
- **Observability hooks** — logging hooks fire on every invocation, demonstrating the hook system

**Streaming:** deployment rollout progress events (scale_replicas emits progress as pods come online)

**Demo script (`demo.py`):** A platform engineer delegates deployment authority to an app team, who delegates to a CI agent. The CI agent lists deployments, checks health, scales replicas (with streaming progress), attempts to delete a resource (denied — scope insufficient, resolution says "request from platform-team"), and the platform engineer reviews the audit showing the aggregated denial entries.

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
