# GTM Regression Harness Report

- Generated at: `2026-04-14T05-20-33Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase2_llm_runtime`
- Passed: `9` / `9`

## Summary By Category

- `clarification`: 3 / 3 passed
- `clarification_followup`: 2 / 2 passed
- `cross_service`: 1 / 1 passed
- `denied`: 1 / 1 passed
- `enrichment_happy_path`: 2 / 2 passed

## Cases

### enrichment-direct-named-accounts [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for Acme Corporation and Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.account_enrichment_summary`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `gtm.account_enrichment_summary`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `account_enrichment_named_accounts`: `PASS`

### enrichment-cross-service-top-risk-q2 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `gtm.account_enrichment_summary`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`
- Data check `account_enrichment_top_risk_q2`: `PASS`

### lookalike-condax [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.lookalike_accounts`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `gtm.lookalike_accounts`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `lookalike_condax`: `PASS`

### clarify-enrichment-missing-account-scope [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for our most important accounts.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `gtm.account_enrichment_summary`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `gtm.account_enrichment_summary`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-lookalike-missing-reference [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts for our best customer.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `gtm.lookalike_accounts`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `gtm.lookalike_accounts`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-then-lookalike-followup [PASS]

- Category: `clarification_followup`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Find lookalike accounts for our best customer.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `gtm.lookalike_accounts`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `gtm.lookalike_accounts`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.lookalike_accounts`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `gtm.lookalike_accounts`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `lookalike_condax`: `PASS`

### clarify-then-enrichment-followup [PASS]

- Category: `clarification_followup`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Summarize firmographic context for our most important accounts.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `gtm.account_enrichment_summary`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `gtm.account_enrichment_summary`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use Acme Corporation and Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.account_enrichment_summary`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `gtm.account_enrichment_summary`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `enrichment`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `account_enrichment_named_accounts`: `PASS`

### clarify-lead-scoring-and-routing [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score these inbound leads and route the hot ones to sales.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### deny-outreach-plus-raw-export [PASS]

- Category: `denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Draft a personalized outreach sequence for the top 5 at-risk accounts in 2017-Q2 and include the raw underlying opportunity rows.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `None`
- Expected capability: `not asserted`
- Actual capability: `None`
- Expected service: `not asserted`
- Actual service: `None`
- Prior service calls: `0`
- Loops: `{'planner_loops': 0, 'service_invoke_loops': 0, 'total_loops': 0}`
