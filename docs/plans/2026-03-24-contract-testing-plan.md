# ANIP Side-Effect Contract Testing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python test harness at `contract-tests/` that verifies ANIP capabilities behave as their manifest declares — read purity, event classification, cost presence, and compensation workflows — with two probe layers (audit-based portable + storage-based optional).

**Architecture:** Generic runner reads the manifest to discover declarations, loads test packs for sample inputs, issues tokens, invokes capabilities, then runs checks via two probe layers. Audit probe works over the ANIP protocol (medium confidence). Storage probe takes before/after DB snapshots (elevated confidence, optional). Results report confidence levels.

**Tech Stack:** Python 3.11+, pytest, httpx, `anip-service` (for storage probe SQLite access).

**Spec:** `docs/specs/2026-03-24-contract-testing-design.md` (PR #96, merges before implementation starts)

---

## File Structure

```
contract-tests/
├── pyproject.toml
├── conftest.py                     # pytest fixtures (base_url, test_pack, storage_dsn)
├── src/anip_contract_tests/
│   ├── __init__.py
│   ├── cli.py                      # anip-contract-tests run ... entry point
│   ├── runner.py                   # Manifest-aware discovery, token issuance, check orchestration
│   ├── probes/
│   │   ├── __init__.py
│   │   ├── audit_probe.py          # Query audit after invocation, examine event_class + cost_actual
│   │   └── storage_probe.py        # Before/after SQLite snapshots with allowlisting
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── read_purity.py          # Read capabilities must not mutate
│   │   ├── classification.py       # event_class must match declared side-effect type
│   │   ├── cost_presence.py        # Financial capabilities must emit cost_actual
│   │   └── compensation.py         # Scenario-driven compensation workflow verification
│   └── report.py                   # Result aggregation with confidence levels
├── packs/
│   ├── travel.json
│   ├── finance.json
│   └── devops.json
└── tests/
    ├── test_probes.py              # Unit tests for audit and storage probes
    ├── test_checks.py              # Unit tests for check logic
    └── test_runner.py              # Integration test with a real ANIP service
```

---

## Task 1: Package Scaffold + Probes

**Files:**
- Create: `contract-tests/pyproject.toml`
- Create: `contract-tests/src/anip_contract_tests/__init__.py`
- Create: `contract-tests/src/anip_contract_tests/probes/__init__.py`
- Create: `contract-tests/src/anip_contract_tests/probes/audit_probe.py`
- Create: `contract-tests/src/anip_contract_tests/probes/storage_probe.py`
- Create: `contract-tests/tests/test_probes.py`

### Audit Probe

```python
class AuditProbe:
    """Query ANIP audit log to examine invocation outcomes."""

    def __init__(self, base_url: str, bearer: str):
        self.base_url = base_url
        self.bearer = bearer

    def get_latest_entry(self, capability: str, invocation_id: str | None = None) -> dict | None:
        """Query audit for the most recent entry for a capability."""

    def check_event_class(self, entry: dict, expected_side_effect: str) -> tuple[str, str]:
        """Compare audit event_class against expected side-effect type.
        Returns (result, detail) — e.g., ("PASS", "low_risk_success matches read")
        """

    def check_cost_actual_present(self, entry: dict) -> tuple[str, str]:
        """Check if cost_actual is present in a successful invocation."""
```

Expected mapping for `check_event_class`:
- `read` → should produce `low_risk_success`
- `write`/`irreversible`/`transactional` → should produce `high_risk_success`

### Storage Probe

```python
class StorageProbe:
    """Take before/after snapshots of the ANIP SQLite database."""

    ALLOWLISTED_TABLES = {"exclusive_leases", "leader_leases"}

    def __init__(self, storage_dsn: str):
        self.db_path = parse_sqlite_path(storage_dsn)

    def snapshot(self) -> dict[str, TableSnapshot]:
        """Snapshot row counts and max sequence for all ANIP tables."""

    def compare(self, before: dict, after: dict, expected_audit_entries: int = 1) -> list[Finding]:
        """Compare snapshots. Returns findings (mutations, warnings).
        Allowlists: the invocation's own audit entry, lease table churn.
        """
```

`TableSnapshot`: row count + max ID/sequence for each table.
`Finding`: `(table, change_type, detail, severity)` — severity is `violation` or `warning`.

### Tests

Unit test the probes with mock data:
- `test_audit_event_class_mapping` — verify read→low_risk, write→high_risk
- `test_storage_snapshot_comparison` — verify mutation detection
- `test_storage_allowlist` — verify lease tables and audit entry are allowlisted

- [ ] Create all files, run tests, commit

```bash
git add contract-tests/
git commit -m "feat(contract-tests): add package scaffold, audit probe, and storage probe"
```

---

## Task 2: Checks + Runner

**Files:**
- Create: `contract-tests/src/anip_contract_tests/checks/__init__.py`
- Create: `contract-tests/src/anip_contract_tests/checks/read_purity.py`
- Create: `contract-tests/src/anip_contract_tests/checks/classification.py`
- Create: `contract-tests/src/anip_contract_tests/checks/cost_presence.py`
- Create: `contract-tests/src/anip_contract_tests/checks/compensation.py`
- Create: `contract-tests/src/anip_contract_tests/runner.py`
- Create: `contract-tests/src/anip_contract_tests/report.py`

### Check Interface

Each check module exposes a function:
```python
async def run(
    capability: str,
    declaration: dict,          # From manifest
    pack_config: dict,          # From test pack for this capability
    audit_probe: AuditProbe,
    storage_probe: StorageProbe | None,
    invoke_result: dict,        # The invocation response
    invocation_id: str,
) -> CheckResult:
```

`CheckResult`:
```python
@dataclass
class CheckResult:
    check_name: str             # e.g., "read_purity", "classification"
    capability: str
    result: str                 # "PASS", "FAIL", "WARN", "SKIP"
    confidence: str             # "medium", "elevated"
    detail: str                 # Human-readable explanation
```

### read_purity.py
- Only runs for capabilities with `side_effect.type == "read"`
- Audit probe: verify `event_class == "low_risk_success"`
- Storage probe (if available): verify no mutations beyond the audit entry
- Returns PASS/FAIL with confidence level

### classification.py
- Runs for all capabilities
- Reads `side_effect.type` from the manifest declaration
- Audit probe: verify `event_class` matches expected mapping
- Returns PASS/FAIL (medium)

### cost_presence.py
- Only runs for capabilities where manifest declares `cost.financial`
- Checks if `cost_actual` is present in the invoke response
- Returns PASS/FAIL (medium)

### compensation.py
- Only runs when the test pack defines `compensation_scenarios`
- Executes the scenario: invoke setup capability → extract result fields → invoke compensation → verify success
- Returns PASS/FAIL (medium)

### Runner

```python
class ContractTestRunner:
    """Discovers capabilities from manifest, runs checks."""

    def __init__(self, base_url: str, test_pack: dict, storage_dsn: str | None = None):
        ...

    async def run_all(self) -> list[CheckResult]:
        """
        1. Fetch manifest
        2. For each capability with sample inputs:
           a. Issue token
           b. Storage probe: before-snapshot (if available)
           c. Invoke capability
           d. Storage probe: after-snapshot (if available)
           e. Audit probe: query latest entry
           f. Run applicable checks
        3. Run compensation scenarios
        4. Return all results
        """
```

### Report

```python
def print_report(results: list[CheckResult]) -> None:
    """Print a formatted report of all check results with confidence levels."""
```

Format:
```
ANIP Contract Test Report
═══════════════════════════════════════
  search_flights
    ✓ read_purity .............. PASS (elevated)
    ✓ classification ........... PASS (medium)
  book_flight
    ✓ classification ........... PASS (medium)
    ✓ cost_presence ............ PASS (medium)
  cancel_booking
    ✓ compensation_workflow .... PASS (medium)
═══════════════════════════════════════
5 passed, 0 failed, 0 warnings, 0 skipped
```

- [ ] Create all files, write unit tests for checks, commit

```bash
git add contract-tests/
git commit -m "feat(contract-tests): add checks (read_purity, classification, cost, compensation) and runner"
```

---

## Task 3: Test Packs + CLI

**Files:**
- Create: `contract-tests/packs/travel.json`
- Create: `contract-tests/packs/finance.json`
- Create: `contract-tests/packs/devops.json`
- Create: `contract-tests/src/anip_contract_tests/cli.py`
- Create: `contract-tests/conftest.py`

### Test Packs

**travel.json:**
```json
{
  "service_id": "anip-travel-showcase",
  "credentials": {
    "bootstrap": {"env": "ANIP_BOOTSTRAP_BEARER", "default": "demo-human-key"}
  },
  "capabilities": {
    "search_flights": {
      "sample_inputs": {"origin": "SEA", "destination": "SFO"}
    },
    "check_availability": {
      "sample_inputs": {"flight_number": "AA100"}
    },
    "book_flight": {
      "sample_inputs": {"flight_number": "DL310"},
      "expects_cost_actual": true
    },
    "cancel_booking": {
      "skip_standalone": true
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

Similar packs for finance and devops, adapted to their capabilities.

### CLI

```python
# contract-tests/src/anip_contract_tests/cli.py
"""anip-contract-tests CLI — run side-effect contract tests."""
import argparse
import asyncio
import sys

from .runner import ContractTestRunner
from .report import print_report


def main():
    parser = argparse.ArgumentParser(prog="anip-contract-tests")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run contract tests")
    run_parser.add_argument("--base-url", required=True)
    run_parser.add_argument("--test-pack", required=True)
    run_parser.add_argument("--storage-dsn", default=None)

    args = parser.parse_args()
    if args.command == "run":
        results = asyncio.run(_run(args))
        print_report(results)
        failures = [r for r in results if r.result == "FAIL"]
        sys.exit(1 if failures else 0)


async def _run(args):
    import json
    with open(args.test_pack) as f:
        pack = json.load(f)
    runner = ContractTestRunner(args.base_url, pack, args.storage_dsn)
    return await runner.run_all()
```

Register as entry point in pyproject.toml:
```toml
[project.scripts]
anip-contract-tests = "anip_contract_tests.cli:main"
```

### conftest.py

pytest fixtures that read `--base-url`, `--test-pack`, `--storage-dsn` from CLI and make them available to test functions.

- [ ] Create all files, commit

```bash
git add contract-tests/
git commit -m "feat(contract-tests): add test packs, CLI, and pytest fixtures"
```

---

## Task 4: Integration Test + Verification

**Files:**
- Create: `contract-tests/tests/test_runner.py`

### Integration test

Start the travel showcase, run the full contract test suite. All commands from the repo root:

```bash
# Start showcase in background (subshell so cd doesn't affect later commands)
(cd examples/showcase/travel && ANIP_STORAGE=sqlite:///showcase.db python3 app.py) &
sleep 3

# Audit-only (medium confidence) — paths are repo-root-relative
anip-contract-tests run \
  --base-url=http://localhost:8000 \
  --test-pack=contract-tests/packs/travel.json

# With storage probe (elevated confidence) — absolute path to the DB
anip-contract-tests run \
  --base-url=http://localhost:8000 \
  --test-pack=contract-tests/packs/travel.json \
  --storage-dsn=sqlite:///$(pwd)/examples/showcase/travel/showcase.db

kill %1
```

Repeat for finance and devops showcases.

Expected: all checks pass. Read capabilities show PASS for read_purity. Financial capabilities show PASS for cost_presence. Compensation scenario succeeds.

- [ ] Run against all 3 showcases, fix any issues, commit

```bash
git add contract-tests/
git commit -m "feat(contract-tests): integration tests passing against all 3 showcases"
```

---

## Task 5: CI Workflow + PR

**Files:**
- Modify: `.github/workflows/ci-python.yml`

- [ ] **Step 1: Add contract-tests to CI trigger paths**

In `.github/workflows/ci-python.yml`, add `contract-tests/**` to the paths filter so changes to the harness trigger CI.

- [ ] **Step 2: Add contract-tests install and test step**

After the existing Python package test steps, add:
```yaml
      - name: Install contract-tests
        run: pip install -e "./contract-tests"

      - name: Test contract-tests unit tests
        run: pytest contract-tests/tests/test_probes.py contract-tests/tests/test_checks.py -v
```

Note: The full integration test (starting a showcase, running the harness against it) is similar to the conformance job pattern. If warranted, add a dedicated `contract-test` CI job that starts the travel showcase and runs `anip-contract-tests run`. For v1, unit tests in the main test job are sufficient.

- [ ] **Step 3: Push and create PR**

```bash
git push -u origin feat/contract-tests
gh pr create --title "feat: add ANIP side-effect contract testing harness"
```
