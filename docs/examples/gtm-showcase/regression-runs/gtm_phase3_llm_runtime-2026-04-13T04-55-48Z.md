# GTM Regression Harness Report

- Generated at: `2026-04-13T04-55-48Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase3_llm_runtime`
- Passed: `9` / `9`

## Summary By Category

- `actor-aware-approval`: 2 / 2 passed
- `actor-aware-enrichment`: 3 / 3 passed
- `actor-aware-read`: 4 / 4 passed

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
- Audit details: `{'actor_id': 'sales_leader', 'service': 'pipeline', 'capability': 'gtm.account_risk_summary', 'min_entries': 1, 'actual_entries': 2}`

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

### phase3-account-manager-east-west-restricted [PASS]

- Category: `actor-aware-read`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Rank the top 5 at-risk accounts in 2017-Q2 for the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.account_risk_summary`
- Expected capability: `gtm.account_risk_summary`
- Actual capability: `gtm.account_risk_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

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

- Approval check: `PASS`
- Approval details: `{'approval_request_id': 'apr_aa333dbe6b80', 'approver_actor_id': 'sales_leader', 'approval_payload': {'actor_id': 'sales_leader', 'approval_request_id': 'apr_aa333dbe6b80', 'result': {'approval': {'approval_request_id': 'apr_aa333dbe6b80', 'approved_at': '2026-04-13T04:55:45.256946+00:00', 'approved_by': {'actor_id': 'sales_leader', 'role': 'sales_leader', 'email': 'human:alex.king@example.com'}, 'capability': 'gtm.prepare_followup_tasks', 'preview': {'owner_scope': 'company', 'quarter': '2017-Q2', 'ranking_basis': 'risk_score', 'requires_approval': True, 'tasks': [{'account_name': 'Betasoloin', 'reason': 'Average risk score 0.94 with 2 open opportunities and max age 246 days.', 'recommended_owner': 'Hayden Neloms', 'regional_office': 'West', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}, {'account_name': 'Betasoloin', 'reason': 'Average risk score 0.94 with 3 open opportunities and max age 256 days.', 'recommended_owner': 'Corliss Cosme', 'regional_office': 'East', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}, {'account_name': 'Condax', 'reason': 'Average risk score 0.94 with 1 open opportunities and max age 222 days.', 'recommended_owner': 'James Ascencio', 'regional_office': 'West', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}, {'account_name': 'Condax', 'reason': 'Average risk score 0.94 with 2 open opportunities and max age 230 days.', 'recommended_owner': 'Cassey Cress', 'regional_office': 'East', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}, {'account_name': 'Dalttechnology', 'reason': 'Average risk score 0.94 with 2 open opportunities and max age 211 days.', 'recommended_owner': 'Markita Hansen', 'regional_office': 'West', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}]}, 'requested_at': '2026-04-13T04:55:45.249086+00:00', 'requested_by': {'actor_id': 'rev_ops_manager', 'email': 'human:priya.shah@example.com', 'role': 'rev_ops_manager'}, 'required_role': 'sales_leader', 'status': 'approved'}}}}`

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
