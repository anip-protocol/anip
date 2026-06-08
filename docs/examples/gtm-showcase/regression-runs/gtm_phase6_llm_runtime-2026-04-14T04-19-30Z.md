# GTM Regression Harness Report

- Generated at: `2026-04-14T04-19-30Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase6_llm_runtime`
- Passed: `5` / `5`

## Summary By Category

- `forecast-actor-aware`: 2 / 2 passed
- `forecast-clarification`: 1 / 1 passed
- `forecast-read`: 2 / 2 passed

## Cases

### phase6-forecast-risk-adjusted-q2 [PASS]

- Category: `forecast-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `What is our risk-adjusted pipeline forecast for 2017-Q2?`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.pipeline_forecast_summary`
- Actual capability: `gtm.pipeline_forecast_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `forecast_summary_risk_adjusted_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'pipeline', 'capability': 'gtm.pipeline_forecast_summary', 'min_entries': 1, 'actual_entries': 20, 'latest_entry': {'capability': 'gtm.pipeline_forecast_summary', 'success': True, 'failure_type': None, 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase6-forecast-best-case-east-q2 [PASS]

- Category: `forecast-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show the best-case pipeline forecast for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.pipeline_forecast_summary`
- Actual capability: `gtm.pipeline_forecast_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `forecast_summary_best_case_east_q2`: `PASS`

### phase6-forecast-clarify-quarter-followup [PASS]

- Category: `forecast-clarification`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `What is our likely pipeline forecast?`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.pipeline_forecast_summary`
- Actual capability: `gtm.pipeline_forecast_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.pipeline_forecast_summary`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.pipeline_forecast_summary`
- Actual capability: `gtm.pipeline_forecast_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `forecast_summary_likely_q2`: `PASS`

### phase6-sales-analyst-forecast-masked [PASS]

- Category: `forecast-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `What is our risk-adjusted pipeline forecast for 2017-Q2?`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.pipeline_forecast_summary`
- Actual capability: `gtm.pipeline_forecast_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `forecast_summary_masked_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'pipeline', 'capability': 'gtm.pipeline_forecast_summary', 'min_entries': 1, 'actual_entries': 6, 'latest_entry': {'capability': 'gtm.pipeline_forecast_summary', 'success': True, 'failure_type': None, 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase6-account-manager-west-forecast-restricted [PASS]

- Category: `forecast-actor-aware`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show the best-case pipeline forecast for 2017-Q2 in the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.pipeline_forecast_summary`
- Actual capability: `gtm.pipeline_forecast_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'account_manager_east', 'service': 'pipeline', 'capability': 'gtm.pipeline_forecast_summary', 'min_entries': 1, 'actual_entries': 6, 'latest_entry': {'capability': 'gtm.pipeline_forecast_summary', 'success': False, 'failure_type': 'restricted', 'root_principal': 'human:maya.chen@example.com|actor_id=account_manager_east|display_name=Maya Chen|role=account_manager|pipeline_scope=East|financial_access=full|enrichment_access=bounded|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`
