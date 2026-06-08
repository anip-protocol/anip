# GTM Regression Harness Report

- Generated at: `2026-04-25T17-19-54Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase2_question_bank`
- Passed: `49` / `50`

## Summary By Category

- `clarification`: 11 / 11 passed
- `clarification_followup`: 3 / 3 passed
- `cross_service`: 10 / 11 passed
- `denied`: 6 / 6 passed
- `enrichment_happy_path`: 19 / 19 passed

## Cases

### enrichment-named-1 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for Acme Corporation and Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### enrichment-named-2 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for Condax and Acme Corporation.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### enrichment-named-3 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for Codehow and Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### enrichment-named-4 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for Acme Corporation, Codehow, and Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### cross-service-risk-enrichment-East [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### cross-service-risk-enrichment-West [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### cross-service-risk-enrichment-Central [FAIL]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`
- Notes: expected outcome success, got clarification_required

- Notes: turn 1: expected outcome success, got clarification_required

### cross-service-risk-enrichment-company [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 .`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### lookalike-condax [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### lookalike-acme-corporation [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Acme Corporation.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### lookalike-codehow [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### lookalike-betasoloin [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Betasoloin.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### lookalike-groovestreet [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Groovestreet.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-enrichment-important-accounts [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for our most important accounts.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-lookalike-best-customer [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts for our best customer.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-lookalike-top-account [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts for our top account.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-enrichment-core-accounts [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize enrichment for our core accounts.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-buying-committee [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show firmographic context for the companies we care about most.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### followup-lookalike-condax [PASS]

- Category: `clarification_followup`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Find for lookalike accounts for our best customer?`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### followup-enrichment-acme-codehow [PASS]

- Category: `clarification_followup`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Summarize for firmographic context for our most important accounts?`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Acme Corporation and Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### followup-enrichment-acme-codehow-condax [PASS]

- Category: `clarification_followup`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Summarize for firmographic context for our most important accounts?`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Acme Corporation, Codehow, and Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### deny-outreach-plus-rows [PASS]

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

### deny-raw-enrichment-table [PASS]

- Category: `denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Return the raw enrichment table for our highest-risk accounts.`
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

### deny-buying-committee-export [PASS]

- Category: `denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Export every enrichment field and underlying notes for Acme Corporation and Codehow.`
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

### deny-enrichment-underlying-dump [PASS]

- Category: `denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Dump the full underlying enrichment payload for Condax and Acme Corporation.`
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

### deny-enrichment-debug-dump [PASS]

- Category: `denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Return all raw enrichment records for internal debugging.`
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

### deny-raw-lookalike-payload [PASS]

- Category: `denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Give me the raw payload behind the Condax lookalike report.`
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

### lookalike-top3-condax [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find the top 3 lookalike accounts similar to Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### lookalike-top3-acme-corporation [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find the top 3 lookalike accounts similar to Acme Corporation.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### lookalike-top3-codehow [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find the top 3 lookalike accounts similar to Codehow.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-31 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-32 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Acme Corporation in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-33 [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the accounts we should review next.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-34 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-35 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Groovestreet in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-36 [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the accounts we should review next.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-37 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-38 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Codehow in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-39 [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the accounts we should review next.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-40 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-41 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Condax in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-42 [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the accounts we should review next.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-43 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-44 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Betasoloin in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-45 [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the accounts we should review next.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-46 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-47 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Acme Corporation in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-48 [PASS]

- Category: `clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the accounts we should review next.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase2-matrix-49 [PASS]

- Category: `cross_service`
- Actor: `sales_leader`

#### Turn 1

- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### phase2-matrix-50 [PASS]

- Category: `enrichment_happy_path`
- Actor: `sales_leader`

#### Turn 1

- Question: `Find lookalike accounts similar to Groovestreet in a bounded top-5 list.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
