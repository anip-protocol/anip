# Phase 7 Live Proof

Phase 7 proves governed scenario composition:

- one compound user question
- multiple bounded service hops
- actor-aware policy still enforced
- approval boundaries still visible
- upstream and downstream checks still auditable

Latest live regression result:

- `14 / 14` passed
  - [gtm_phase7_llm_runtime-latest.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase7_llm_runtime-latest.md)

The current compound scenarios are:

1. `prioritization -> enrichment -> outreach`
- question:
  - `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account.`
- result:
  - planned capability `gtm.prioritize_accounts`
  - final capability `gtm.draft_outreach_message`
  - `2` prior service calls
  - `4` total loops

2. `forecast -> risk -> follow-up preview`
- question:
  - `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts.`
- result:
  - planned capability `gtm.pipeline_forecast_summary`
  - final capability `gtm.prepare_followup_tasks`
  - `approval_required`
  - `2` prior service calls
  - `4` total loops

3. actor-aware denial on the same compound ask
- actor:
  - `sales_analyst`
- result:
  - same compound flow reaches `gtm.prepare_followup_tasks`
  - final governed outcome is `denied`

4. `score -> route`
- question:
  - `Score inbound leads from last week, route the hot ones to sales, and draft a first-touch email for the highest-priority account.`
- result:
  - planned capability `gtm.score_leads`
  - final capability `gtm.route_leads`
  - `approval_required`
  - `1` prior service call
  - `3` total loops

The broader Phase 7 pack now also covers:

- `bottleneck -> risk -> enrichment`
- `bottleneck -> risk -> follow-up preview`
- `bottleneck -> risk -> enrichment -> outreach` with a safe clarification stop
- `prioritization -> enrichment -> outreach` with channel variation
  - `email`
  - `linkedin`
- `prioritization -> enrichment -> outreach` with objective variation
  - `first_touch`
  - `follow_up`
- direct `route_leads` approval and denial variants where the planner legally
  skips the scoring hop and still stays inside the governed capability surface
- regional forecast-plus-follow-up variants with actor-aware approval vs denial

What this phase demonstrates:

- the runtime can compose across services without turning into a prompt-owned workflow engine
- each hop still uses declared ANIP capabilities
- approval is not skipped mid-chain
- actor-aware denial still applies on compound scenarios
- the harness can validate both the service chain and the business result

Useful summary line:

- the question is compound, the execution is still governed
