# GTM Regression Harness Report

- Generated at: `2026-04-13T04-35-05Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase3_llm_runtime`
- Passed: `8` / `8`

## Summary By Category

- `actor-aware-approval`: 2 / 2 passed
- `actor-aware-enrichment`: 3 / 3 passed
- `actor-aware-read`: 3 / 3 passed

## Cases

### phase3-sales-leader-risk-summary [PASS]

- Category: `actor-aware-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Rank the top 10 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `gtm.account_risk_summary`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `risk_summary_top10_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'pipeline', 'capability': 'gtm.account_risk_summary', 'min_entries': 1, 'actual_entries': 8}`

### phase3-sales-analyst-risk-summary-masked [PASS]

- Category: `actor-aware-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Rank the top 10 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `gtm.account_risk_summary`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `risk_summary_masked_top10_q2`: `PASS`

### phase3-account-manager-east-scope [PASS]

- Category: `actor-aware-read`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Rank the top 5 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `gtm.account_risk_summary`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `risk_summary_top5_east_q2`: `PASS`

### phase3-sales-analyst-followup-denied [PASS]

- Category: `actor-aware-approval`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_followup_tasks`
- Expected capability: `gtm.prepare_followup_tasks`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase3-rev-ops-followup-approval [PASS]

- Category: `actor-aware-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_followup_tasks`
- Expected capability: `gtm.prepare_followup_tasks`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase3-sales-analyst-bounded-enrichment [PASS]

- Category: `actor-aware-enrichment`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Summarize firmographic context for Acme Corporation and Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `gtm.account_enrichment_summary`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `account_enrichment_named_accounts_bounded`: `PASS`

### phase3-sales-analyst-lookalike-denied [PASS]

- Category: `actor-aware-enrichment`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Find lookalike accounts similar to Condax.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `gtm.lookalike_accounts`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase3-sales-leader-lookalike-success [PASS]

- Category: `actor-aware-enrichment`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `gtm.lookalike_accounts`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `lookalike_condax`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'enrichment', 'capability': 'gtm.lookalike_accounts', 'min_entries': 1, 'actual_entries': 5}`
