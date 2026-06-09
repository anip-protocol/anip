# GTM Regression Harness Report

- Generated at: `2026-04-25T22-40-36Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase3_question_bank`
- Passed: `50` / `50`

## Summary By Category

- `actor-aware-core`: 10 / 10 passed
- `actor-aware-matrix`: 30 / 30 passed
- `actor-aware-variant`: 10 / 10 passed

## Cases

### actor-core-1 [PASS]

- Category: `actor-aware-core`
- Actor: `sales_leader`

#### Turn 1

- Question: `Rank the top 10 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-2 [PASS]

- Category: `actor-aware-core`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Rank the top 10 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-3 [PASS]

- Category: `actor-aware-core`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Rank the top 5 at-risk accounts in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-4 [PASS]

- Category: `actor-aware-core`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Rank the top 5 at-risk accounts in 2017-Q2 for the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-5 [PASS]

- Category: `actor-aware-core`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_followup_tasks`
- Expected capability: `not asserted`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-6 [PASS]

- Category: `actor-aware-core`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_followup_tasks`
- Expected capability: `not asserted`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-7 [PASS]

- Category: `actor-aware-core`
- Actor: `sales_analyst`

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

### actor-core-8 [PASS]

- Category: `actor-aware-core`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Find lookalike accounts similar to Condax.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-core-9 [PASS]

- Category: `actor-aware-core`
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

### actor-core-10 [PASS]

- Category: `actor-aware-core`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region with a stage breakdown.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-1 [PASS]

- Category: `actor-aware-variant`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show the top 5 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-2 [PASS]

- Category: `actor-aware-variant`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show the top 5 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-3 [PASS]

- Category: `actor-aware-variant`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show the top 5 at-risk accounts in 2017-Q2 for the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-4 [PASS]

- Category: `actor-aware-variant`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show the top 5 at-risk accounts in 2017-Q2 for the Central region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-5 [PASS]

- Category: `actor-aware-variant`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Prepare follow-up tasks for the top 3 at-risk accounts in the East region for 2017-Q2.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_followup_tasks`
- Expected capability: `not asserted`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-6 [PASS]

- Category: `actor-aware-variant`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prepare follow-up tasks for the top 3 at-risk accounts in the East region for 2017-Q2.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_followup_tasks`
- Expected capability: `not asserted`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-7 [PASS]

- Category: `actor-aware-variant`
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

### actor-variant-8 [PASS]

- Category: `actor-aware-variant`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Find lookalike accounts similar to Acme Corporation.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.lookalike_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.lookalike_accounts`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-variant-9 [PASS]

- Category: `actor-aware-variant`
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

### actor-variant-10 [PASS]

- Category: `actor-aware-variant`
- Actor: `sales_analyst`

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

### actor-matrix-21 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-22 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-23 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-24 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-25 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-26 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-27 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-28 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-29 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-30 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-31 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-32 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-33 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-34 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-35 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-36 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-37 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-38 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-39 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-40 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-41 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-42 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-43 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-44 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-45 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-46 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-47 [PASS]

- Category: `actor-aware-matrix`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-48 [PASS]

- Category: `actor-aware-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the Central region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-49 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### actor-matrix-50 [PASS]

- Category: `actor-aware-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show pipeline health for 2017-Q2 in the West region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.pipeline_summary`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
