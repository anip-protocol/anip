# ANIP Side-Effect Contract Testing — Design Spec

## Purpose

A test harness that verifies ANIP capabilities behave as their manifest declares. Catches mismatches between declared side-effect types, cost posture, and event classification versus observed behavior. This strengthens ANIP's core promise: the system tells the agent what a capability will do, and that declaration is truthful.

## Location

Top-level `contract-tests/` directory, separate from `conformance/`. Conformance tests protocol correctness ("does your ANIP implementation speak the protocol?"). Contract tests verify behavioral truthfulness ("does your service do what it says it does?").

## Architecture

```
contract-tests/
├── pyproject.toml
├── src/anip_contract_tests/
│   ├── __init__.py
│   ├── cli.py             # anip-contract-tests run ... entry point
│   ├── runner.py           # Discovers capabilities from manifest, runs checks
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── read_purity.py      # Verify read capabilities don't mutate
│   │   ├── classification.py   # Verify event_class matches declared side-effect
│   │   ├── cost_presence.py    # Verify cost_actual present for financial capabilities
│   │   └── transactional.py    # Scenario-driven: verify rollback/compensation
│   ├── probes/
│   │   ├── __init__.py
│   │   ├── audit_probe.py      # Audit-based detection (portable)
│   │   └── storage_probe.py    # Storage snapshot comparison (optional, deeper)
│   └── report.py           # Result aggregation with confidence levels
├── packs/
│   ├── travel.json          # Test pack for travel showcase
│   ├── finance.json         # Test pack for finance showcase
│   └── devops.json          # Test pack for devops showcase
└── conftest.py              # pytest fixtures
```

## Two Probe Layers

### Audit Probe (portable, medium confidence)

Works over the ANIP protocol itself. After invocation, queries `POST /anip/audit` and examines:
- `event_class` — does it match what the declared side-effect type should produce?
- `cost_actual` — is it present when the capability declares financial cost?
- `success`/`failure_type` — does the outcome match expectations?

**Confidence: medium.** This trusts the service's own classification. A buggy or dishonest implementation could mutate state and still emit `low_risk_success`. The audit probe is a supporting signal, not proof of purity.

### Storage Probe (optional, elevated confidence)

Requires `--storage-dsn` pointing to the service's database. Before invocation, snapshots relevant tables. After invocation, compares for mutations.

For SQLite: snapshots `audit_log` max sequence, row counts and checksums for `tokens`, `checkpoints`, and ANIP-managed tables.
For PostgreSQL: same approach via connection.

**Confidence: elevated (not high).** This probe is stronger than audit-only but has known limitations:
- Row-count-based snapshots miss in-place updates (UPDATE without INSERT/DELETE)
- ANIP background workers (retention sweeper, checkpoint scheduler, aggregation flusher) can produce legitimate mutations between the before and after snapshots
- The probe must allowlist expected internal state changes (new audit entry from the invocation itself, retention deletions, checkpoint creation)

To reduce false positives, the storage probe:
1. Pauses briefly before the after-snapshot to let the invocation settle
2. Allowlists the audit entry created by the invocation itself
3. Ignores `leader_leases` and `exclusive_leases` tables (lease churn is normal)
4. Reports unexpected mutations as findings, not hard failures, when background workers may be active

The storage probe is optional. When absent, the harness runs audit-only checks at medium confidence. When present, both probes run and confidence is elevated (but not absolute).

## Check Types

### 1. Read Purity

**What it checks:** A capability declaring `side_effect.type = read` should not mutate persistent state beyond its own audit entry.

**Audit probe:** After invocation, verify `event_class` is `low_risk_success` (not `high_risk_success`).

**Storage probe:** Before/after snapshot comparison. Expected changes: the new audit entry from the invocation itself. Other changes are flagged, but allowlisted internal mutations (lease churn, retention sweeps) are reported as WARN, not FAIL.

### 2. Event Classification

**What it checks:** Every capability's audit `event_class` should match its declared side-effect type.

Expected mapping:
- `read` → `low_risk_success` (on success)
- `write` / `irreversible` / `transactional` → `high_risk_success` (on success)

**Audit probe only.** Reads the side-effect type from the manifest (not from the test pack — the manifest is the source of truth). Invokes the capability, queries audit, verifies the classification.

### 3. Cost Presence

**What it checks:** If a capability declares `cost.financial` in its manifest, a successful invocation should include `cost_actual` in the response.

**Verification:** Invoke the capability with sample inputs from the test pack. Check the response for `cost_actual` being present and non-null.

This is conservative for v1: it verifies presence, not range accuracy. Range validation ("is `cost_actual` within the declared `range_min`/`range_max`?") is a future enhancement once the declaration format is precise enough to support it reliably.

### 4. Compensation Workflow Verification (scenario-driven)

**What it checks:** For capabilities that declare a compensation path (e.g., a `transactional` capability paired with a cancellation capability), the harness verifies the compensation workflow succeeds.

**Important distinction:** This does NOT test ANIP's formal transactional semantics — atomic rollback within the declared rollback window, auto-rollback on timeout, etc. True transactional verification would require deeper runtime integration (injecting failures, observing auto-rollback) which is out of scope for v1. What this check does test is that a declared compensation path actually works end-to-end.

The test pack defines the workflow:
```json
{
  "compensation_scenarios": [
    {
      "setup_capability": "book_flight",
      "setup_inputs": {"flight_number": "DL310"},
      "compensation_capability": "cancel_booking",
      "compensation_inputs_from_result": {"booking_id": "result.booking_id"},
      "verify": "compensation_succeeds"
    }
  ]
}
```

This is explicitly scenario-driven, not generic. The harness provides the runner; the test pack provides the domain knowledge. Full transactional semantics testing (atomic guarantees, rollback window enforcement) is a future enhancement requiring runtime-level hooks.

## Test Packs

JSON files providing sample inputs, credential references, and scenario definitions per service. The manifest is the source of truth for declarations — packs do NOT repeat `expected_side_effect`.

```json
{
  "service_id": "anip-travel-showcase",
  "credentials": {
    "bootstrap": {"env": "ANIP_BOOTSTRAP_BEARER", "default": "demo-human-key"},
    "agent": {"env": "ANIP_AGENT_BEARER", "default": "demo-agent-key"}
  },
  "capabilities": {
    "search_flights": {
      "sample_inputs": {"origin": "SEA", "destination": "SFO"}
    },
    "book_flight": {
      "sample_inputs": {"flight_number": "AA100"},
      "expects_cost_actual": true
    },
    "cancel_booking": {
      "skip_standalone": true,
      "note": "Tested via transactional scenario only"
    }
  },
  "compensation_scenarios": [
    {
      "setup_capability": "book_flight",
      "setup_inputs": {"flight_number": "DL310"},
      "compensation_capability": "cancel_booking",
      "compensation_inputs_from_result": {"booking_id": "result.booking_id"},
      "verify": "compensation_succeeds"
    }
  ]
}
```

Key design decisions:
- **Credentials via env vars** — `{"env": "ANIP_BOOTSTRAP_BEARER", "default": "demo-human-key"}`. Never hardcode secrets. Defaults are for local dev only.
- **Manifest is source of truth** — side-effect types, cost declarations, scope requirements come from the live manifest, not the pack.
- **`skip_standalone`** — some capabilities (like `cancel_booking`) only make sense as part of a workflow, not standalone.

## CLI

Primary interface: a CLI wrapper around pytest.

```bash
# Install
pip install -e ./contract-tests

# Run against travel showcase (audit probe only)
anip-contract-tests run \
  --base-url=http://localhost:8000 \
  --test-pack=contract-tests/packs/travel.json

# Run with storage probing (higher confidence)
anip-contract-tests run \
  --base-url=http://localhost:8000 \
  --test-pack=contract-tests/packs/travel.json \
  --storage-dsn=sqlite:///showcase.db
```

Also works directly via pytest:
```bash
pytest contract-tests/ \
  --base-url=http://localhost:8000 \
  --test-pack=contract-tests/packs/travel.json
```

## Confidence Reporting

Each check reports a result with a confidence level:

| Result | Meaning |
|--------|---------|
| `PASS (elevated)` | Both probes agree — no violations detected. Storage probe has known limitations (see above). |
| `PASS (medium)` | Audit probe only — no violations in audit trail, but state not independently verified |
| `FAIL (elevated)` | Storage probe detected an unexpected mutation |
| `FAIL (medium)` | Audit probe detected a classification mismatch |
| `WARN (elevated)` | Storage probe found changes that may be background worker activity — requires manual review |
| `SKIP` | Capability skipped (no sample inputs, skip_standalone, etc.) |

The report clearly distinguishes confidence levels so operators know how much to trust a passing result. No result claims "high confidence" — the strongest claim is "elevated" because the storage probe has known blind spots.

## Runner Flow

1. Fetch manifest from `GET /anip/manifest`
2. Load test pack
3. For each capability in the manifest:
   a. Read declaration from manifest (side-effect type, cost, scope)
   b. Find sample inputs from test pack (skip if none)
   c. Issue a token with appropriate scope
   d. If storage probe available: take before-snapshot
   e. Invoke the capability
   f. If storage probe available: take after-snapshot, compare
   g. Query audit for the invocation
   h. Run applicable checks (read purity, classification, cost presence)
4. Run transactional scenarios from test pack
5. Generate report with confidence levels

## What This Does NOT Cover

- Full formal verification of side-effect semantics
- Automatic test generation without sample inputs
- Cross-service contract testing (federated trust not yet implemented)
- Runtime contract monitoring (this is a test harness, not a production guard)
- Cost range validation (v1 checks presence only)
- Write capability mutation verification (what constitutes "correct" mutation is domain-specific)

## First Pass

Python only. Three test packs for the showcase apps (travel, finance, devops). Validates the harness design before expanding.
