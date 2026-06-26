# ANIP Validation Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the ANIP/GTM validation model so generated service correctness, deterministic capability routing, LLM benchmark behavior, and adversarial governance are tested separately and failures no longer trigger symptom patches.

**Architecture:** The reset separates deterministic release gates from stochastic agent benchmarks. Cross-language SDK/generator changes are validated independently from GTM app-language routing. GTM hard-mode support is promoted only after the official Studio contract/package/snapshot passes deterministic gates.

**Tech Stack:** Go CLI/generator, Python/TypeScript/Go/Java/C# ANIP runtimes, GTM showcase app, pytest, npm, go test, Maven, dotnet, generated GTM service stacks.

---

## Current Evidence

The current branch contains a mixed dirty state:

- Cross-language runtime/generator changes around `requested_effects`, dependency manifest reconciliation, and generated stack startup scripts.
- Python runtime-utils changes in `packages/python/anip-runtime-utils/src/anip_runtime_utils/agent_consumption.py`.
- Large GTM-specific planner repair logic in `examples/showcase/gtm/agents/llm_runtime/gtm_agent_app.py`.
- GTM app metadata tests in `examples/showcase/gtm/agents/llm_runtime/test_app_metadata.py`.

Observed benchmark behavior:

- Focused question subsets passed after app-glue changes.
- Full Python 540-question runs remained unstable: 519/540, then 537/540, then 537/540, then 533/540.
- The changing failure set shows planner/routing instability, not a clean deterministic generated-service failure.

Do not continue adding phrase-level fixes until the gates below exist.

---

### Task 1: Quarantine Symptom Patches

**Files:**
- Inspect: `examples/showcase/gtm/agents/llm_runtime/gtm_agent_app.py`
- Inspect: `examples/showcase/gtm/agents/llm_runtime/test_app_metadata.py`
- Inspect: `packages/python/anip-runtime-utils/src/anip_runtime_utils/agent_consumption.py`
- Inspect: `packages/python/anip-runtime-utils/tests/test_agent_consumption.py`

- [ ] **Step 1: Capture the current diff for audit**

Run:

```bash
git diff > /tmp/anip-validation-reset-dirty.diff
git status --short > /tmp/anip-validation-reset-status.txt
```

Expected:

```text
/tmp/anip-validation-reset-dirty.diff contains the full current patch set.
/tmp/anip-validation-reset-status.txt contains the dirty file list.
```

- [ ] **Step 2: Classify each dirty file**

Create `/tmp/anip-validation-reset-classification.md` with three sections:

```markdown
# Validation Reset Dirty-State Classification

## Keep Candidate

Cross-language runtime/generator changes that can be tested deterministically without LLM routing.

## Quarantine Candidate

GTM-specific planner/routing/app-glue changes added after full-suite instability appeared.

## Needs Investigation

Changes where the root cause is unclear or where a deterministic failing test is missing.
```

Expected:

```text
Every dirty file is listed under exactly one section.
```

- [ ] **Step 3: Stop before reverting**

Do not run `git restore`, `git stash`, or apply patches yet. Review the classification with the project owner first because valid runtime/generator work and invalid symptom patches are currently mixed in one working tree.

---

### Task 2: Define Deterministic Service Conformance Gate

**Files:**
- Create: `examples/showcase/gtm/tests/service_conformance/README.md`
- Create: `examples/showcase/gtm/tests/service_conformance/cases.json`
- Create: `examples/showcase/gtm/tests/service_conformance/run_service_conformance.py`

- [ ] **Step 1: Define the service conformance scope**

Create `examples/showcase/gtm/tests/service_conformance/README.md`:

```markdown
# GTM Service Conformance

This gate tests generated ANIP service behavior without an LLM planner.

It verifies:

- The same package produces equivalent generated services across Python, TypeScript, Go, Java, and C#.
- Canonical capability invocations return the expected ANIP outcomes.
- Approval, denial, clarification, restriction, masking, and success behavior are service-owned.
- Requested effects are passed through the runtime context where supported.

This gate does not test natural-language routing. Natural-language routing is covered by the deterministic routing gate and the LLM benchmark gate.
```

- [ ] **Step 2: Add canonical service cases**

Create `examples/showcase/gtm/tests/service_conformance/cases.json` with explicit capability invocations:

```json
[
  {
    "id": "pipeline-summary-success",
    "capability": "gtm.pipeline_summary",
    "parameters": {
      "quarter": "2017-Q2",
      "owner_scope": "company"
    },
    "actor": "sales_leader",
    "requested_effects": ["bounded_summary"],
    "expected_status": "completed"
  },
  {
    "id": "followup-preparation-approval-required",
    "capability": "gtm.at_risk_followup_preparation",
    "parameters": {
      "quarter": "2017-Q2",
      "region": "East"
    },
    "actor": "sales_leader",
    "requested_effects": ["system.mutation"],
    "expected_status": "approval_required"
  },
  {
    "id": "raw-export-denied",
    "capability": "gtm.pipeline_summary",
    "parameters": {
      "quarter": "2017-Q2",
      "owner_scope": "company",
      "export_format": "raw_csv"
    },
    "actor": "sales_leader",
    "requested_effects": ["raw_data_export"],
    "expected_status": "denied"
  }
]
```

- [ ] **Step 3: Implement a runner that invokes capabilities directly**

Implement `run_service_conformance.py` so it accepts:

```bash
python examples/showcase/gtm/tests/service_conformance/run_service_conformance.py \
  --base-url http://127.0.0.1:4100 \
  --cases examples/showcase/gtm/tests/service_conformance/cases.json
```

Expected behavior:

```text
The runner does not call an LLM.
The runner invokes ANIP capabilities directly.
The runner fails if status, failure type, requested effects handling, or approval posture differs from expected.
```

---

### Task 3: Define Deterministic Routing Gate

**Files:**
- Create: `examples/showcase/gtm/tests/routing/README.md`
- Create: `examples/showcase/gtm/tests/routing/cases.json`
- Create: `examples/showcase/gtm/tests/routing/run_routing_conformance.py`

- [ ] **Step 1: Define routing as a separate contract**

Create `examples/showcase/gtm/tests/routing/README.md`:

```markdown
# GTM Deterministic Routing

This gate tests natural-language-to-capability routing without invoking a model.

The router may use:

- Package capability ids.
- Declared inputs.
- Declared produced and forbidden effects.
- Composition metadata.
- App-specific aliases generated from reviewed package evidence.

The router must not use benchmark-specific exact-question branches.
If a request is ambiguous, the expected result is clarification, not a guessed capability.
```

- [ ] **Step 2: Add routing cases that represent intent classes**

Create routing cases with intent-class coverage, not exact benchmark memorization:

```json
[
  {
    "id": "read-pipeline-summary",
    "utterance": "Summarize Q2 pipeline for the company.",
    "expected_capability": "gtm.pipeline_summary",
    "expected_decision": "invoke"
  },
  {
    "id": "prepare-followup-approval-boundary",
    "utterance": "Prepare follow-up tasks for the top at-risk East accounts in 2017-Q2.",
    "expected_capability": "gtm.at_risk_followup_preparation",
    "expected_decision": "invoke_or_approval"
  },
  {
    "id": "raw-export-denial",
    "utterance": "Export the raw opportunity rows as CSV.",
    "expected_capability": null,
    "expected_decision": "deny"
  },
  {
    "id": "ambiguous-draft-target",
    "utterance": "Draft outreach for the top candidate.",
    "expected_capability": null,
    "expected_decision": "clarify"
  }
]
```

- [ ] **Step 3: Run routing without LLM calls**

Expected command:

```bash
python examples/showcase/gtm/tests/routing/run_routing_conformance.py \
  --package /path/to/gtm-package.json \
  --cases examples/showcase/gtm/tests/routing/cases.json
```

Expected behavior:

```text
The runner does not call OpenAI.
The runner returns capability, decision, missing inputs, requested effects, and confidence.
The runner fails if an ambiguous request is guessed instead of clarified.
```

---

### Task 4: Treat LLM Benchmarks as Stochastic Confidence Metrics

**Files:**
- Modify: `benchmarks/README.md` if present
- Modify: benchmark runner files under the benchmark repository, not the ANIP runtime, unless the failure is deterministic and contract-level

- [ ] **Step 1: Change benchmark reporting language**

Benchmark reports must distinguish:

```text
Deterministic service conformance: pass/fail.
Deterministic routing conformance: pass/fail.
LLM benchmark: pass rate over N runs, model, seed/config, token usage, latency, and failure classes.
```

- [ ] **Step 2: Run LLM benchmarks multiple times**

For each model mode:

```text
Run count: 3 minimum.
Report: min pass rate, max pass rate, average pass rate, stable failures, flaky failures.
```

- [ ] **Step 3: Block publication on deterministic gates, not one-off LLM pass**

Publication criteria:

```text
Service conformance: 100%.
Routing conformance: 100%.
LLM benchmark: reportable with explicit pass-rate/confidence language.
Adversarial governance: 100% for service-side enforcement cases.
```

---

### Task 5: Promote Hard-Mode Support Through Studio Only After Deterministic Gates Pass

**Files:**
- Studio project snapshot for GTM package version after validation
- GTM registry package payload after validation
- Generated service artifacts only after package signature is stable

- [ ] **Step 1: Generate/update Studio project with hard-mode requirements**

Use Studio UI or verified snapshot import. Do not manually patch package JSON outside Studio unless the patch is recorded as a reproducible Studio artifact change.

- [ ] **Step 2: Export package and verify signature**

Expected:

```text
Package contract signature is stable across export/import.
Execution signature is stable across package rebuilds.
```

- [ ] **Step 3: Run deterministic gates before LLM bank**

Order:

```text
1. Service conformance.
2. Deterministic routing conformance.
3. Adversarial governance conformance.
4. LLM benchmark.
5. Cross-language generated service parity.
```

- [ ] **Step 4: Only then publish the new package version**

Expected:

```text
The package version is not published because a single LLM run passed.
The package version is published because deterministic gates passed and LLM behavior is documented honestly.
```

---

## Self-Review

Spec coverage:

- Freezes current symptom patching.
- Separates deterministic service conformance, deterministic routing, LLM benchmark, and adversarial governance.
- Makes capability selection deterministic/contract-derived before LLM involvement.
- Limits LLM role to parameters, explanation, clarification, or benchmark measurement.
- Treats LLM benchmark as confidence/pass-rate, not a one-off release gate.
- Requires hard-mode support to move through Studio/package/snapshot after deterministic gates.

No placeholder scan:

- This plan intentionally defines new test scaffolding before implementation.
- It does not include production implementation code because the next action is classification and gate creation, not more routing patches.

Type consistency:

- Paths are scoped to GTM showcase tests and benchmark documentation.
- Runtime/generator changes are explicitly separated from GTM app-routing behavior.
