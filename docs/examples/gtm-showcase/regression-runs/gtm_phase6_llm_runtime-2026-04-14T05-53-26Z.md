# GTM Regression Harness Report

- Generated at: `2026-04-14T05-53-26Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase6_llm_runtime`
- Passed: `18` / `18`

## Summary By Category

- `bottleneck-actor-aware`: 2 / 2 passed
- `bottleneck-clarification`: 1 / 1 passed
- `bottleneck-read`: 2 / 2 passed
- `forecast-actor-aware`: 2 / 2 passed
- `forecast-clarification`: 1 / 1 passed
- `forecast-read`: 2 / 2 passed
- `product-pipeline-actor-aware`: 1 / 1 passed
- `product-pipeline-read`: 1 / 1 passed
- `reassignment-preview`: 3 / 3 passed
- `team-performance-actor-aware`: 1 / 1 passed
- `team-performance-clarification`: 1 / 1 passed
- `team-performance-read`: 1 / 1 passed

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
- Audit details: `{'actor_id': 'sales_leader', 'service': 'pipeline', 'capability': 'gtm.pipeline_forecast_summary', 'min_entries': 1, 'actual_entries': 5, 'latest_entry': {'capability': 'gtm.pipeline_forecast_summary', 'success': True, 'failure_type': None, 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

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
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'pipeline', 'capability': 'gtm.pipeline_forecast_summary', 'min_entries': 1, 'actual_entries': 2, 'latest_entry': {'capability': 'gtm.pipeline_forecast_summary', 'success': True, 'failure_type': None, 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

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
- Audit details: `{'actor_id': 'account_manager_east', 'service': 'pipeline', 'capability': 'gtm.pipeline_forecast_summary', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.pipeline_forecast_summary', 'success': False, 'failure_type': 'restricted', 'root_principal': 'human:maya.chen@example.com|actor_id=account_manager_east|display_name=Maya Chen|role=account_manager|pipeline_scope=East|financial_access=full|enrichment_access=bounded|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase6-bottleneck-regional-q2 [PASS]

- Category: `bottleneck-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Where are the biggest stage bottlenecks in our 2017-Q2 pipeline?`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `gtm.stage_bottleneck_summary`
- Actual capability: `gtm.stage_bottleneck_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `bottleneck_summary_regional_q2`: `PASS`

### phase6-bottleneck-product-east-q2 [PASS]

- Category: `bottleneck-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show the biggest stage bottlenecks by product for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `gtm.stage_bottleneck_summary`
- Actual capability: `gtm.stage_bottleneck_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `bottleneck_summary_product_east_q2`: `PASS`

### phase6-bottleneck-clarify-quarter-followup [PASS]

- Category: `bottleneck-clarification`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Where are we bottlenecked?`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `gtm.stage_bottleneck_summary`
- Actual capability: `gtm.stage_bottleneck_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.stage_bottleneck_summary`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `gtm.stage_bottleneck_summary`
- Actual capability: `gtm.stage_bottleneck_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `bottleneck_summary_regional_q2`: `PASS`

### phase6-sales-analyst-bottleneck-masked [PASS]

- Category: `bottleneck-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Where are the biggest stage bottlenecks in our 2017-Q2 pipeline?`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `gtm.stage_bottleneck_summary`
- Actual capability: `gtm.stage_bottleneck_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `bottleneck_summary_masked_q2`: `PASS`

### phase6-account-manager-west-bottleneck-restricted [PASS]

- Category: `bottleneck-actor-aware`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show the biggest stage bottlenecks in the West region for 2017-Q2.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `gtm.stage_bottleneck_summary`
- Actual capability: `gtm.stage_bottleneck_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'account_manager_east', 'service': 'pipeline', 'capability': 'gtm.stage_bottleneck_summary', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.stage_bottleneck_summary', 'success': False, 'failure_type': 'restricted', 'root_principal': 'human:maya.chen@example.com|actor_id=account_manager_east|display_name=Maya Chen|role=account_manager|pipeline_scope=East|financial_access=full|enrichment_access=bounded|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase6-sales-team-performance-q2 [PASS]

- Category: `team-performance-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `How are our sales teams performing in 2017-Q2?`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.sales_team_performance_summary`
- Expected capability: `gtm.sales_team_performance_summary`
- Actual capability: `gtm.sales_team_performance_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `sales_team_performance_manager_q2`: `PASS`

### phase6-sales-team-clarify-quarter-followup [PASS]

- Category: `team-performance-clarification`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `How are the teams performing?`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.sales_team_performance_summary`
- Expected capability: `gtm.sales_team_performance_summary`
- Actual capability: `gtm.sales_team_performance_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.sales_team_performance_summary`
- Actual planned capability: `gtm.sales_team_performance_summary`
- Expected capability: `gtm.sales_team_performance_summary`
- Actual capability: `gtm.sales_team_performance_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `sales_team_performance_manager_q2`: `PASS`

### phase6-sales-team-west-restricted [PASS]

- Category: `team-performance-actor-aware`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Show sales team performance for 2017-Q2 in the West region.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.sales_team_performance_summary`
- Expected capability: `gtm.sales_team_performance_summary`
- Actual capability: `gtm.sales_team_performance_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'account_manager_east', 'service': 'pipeline', 'capability': 'gtm.sales_team_performance_summary', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.sales_team_performance_summary', 'success': False, 'failure_type': 'restricted', 'root_principal': 'human:maya.chen@example.com|actor_id=account_manager_east|display_name=Maya Chen|role=account_manager|pipeline_scope=East|financial_access=full|enrichment_access=bounded|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase6-product-pipeline-east-q2 [PASS]

- Category: `product-pipeline-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show product pipeline performance for 2017-Q2 in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.product_pipeline_summary`
- Expected capability: `gtm.product_pipeline_summary`
- Actual capability: `gtm.product_pipeline_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `product_pipeline_east_q2`: `PASS`

### phase6-product-pipeline-masked [PASS]

- Category: `product-pipeline-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show product pipeline performance for 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.product_pipeline_summary`
- Expected capability: `gtm.product_pipeline_summary`
- Actual capability: `gtm.product_pipeline_summary`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `product_pipeline_masked_q2`: `PASS`

### phase6-reassignment-plan-approval [PASS]

- Category: `reassignment-preview`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Prepare a reassignment plan for overloaded managers in 2017-Q2.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_reassignment_plan`
- Expected capability: `gtm.prepare_reassignment_plan`
- Actual capability: `gtm.prepare_reassignment_plan`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `reassignment_preview_manager_capacity_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'rev_ops_manager', 'service': 'pipeline', 'capability': 'gtm.prepare_reassignment_plan', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.prepare_reassignment_plan', 'success': False, 'failure_type': 'approval_required', 'root_principal': 'human:priya.shah@example.com|actor_id=rev_ops_manager|display_name=Priya Shah|role=rev_ops_manager|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

- Approval check: `PASS`
- Approval details: `{'approval_request_id': 'apr_a895e53a26cb', 'approver_actor_id': 'sales_leader', 'pending_visible': True, 'approved_visible': True, 'approval_payload': {'actor_id': 'sales_leader', 'approval_request_id': 'apr_a895e53a26cb', 'service': 'pipeline', 'result': {'approval': {'approval_request_id': 'apr_a895e53a26cb', 'approved_at': '2026-04-14T05:53:23.722216+00:00', 'approved_by': {'actor_id': 'sales_leader', 'role': 'sales_leader', 'email': 'human:alex.king@example.com'}, 'capability': 'gtm.prepare_reassignment_plan', 'preview': {'owner_scope': 'company', 'quarter': '2017-Q2', 'reassignments': [{'account_name': 'Iselectrics', 'days_since_engage': 274, 'deal_stage': 'Engaging', 'expected_impact': "Reduce Summer Sewald's open load by one and move a high-attention opportunity to Celia Rouche within West.", 'opportunity_id': 'YLK0MRJ3', 'product_name': 'GTX Basic', 'reason': 'Summer Sewald is carrying 124 open opportunities in West; this opportunity has been open 274 days with risk score 0.86.', 'risk_score': 0.86, 'sales_agent_name': 'Kary Hendrixson', 'source_manager': 'Summer Sewald', 'source_open_load': 124, 'source_region': 'West', 'target_manager': 'Celia Rouche', 'target_open_load': 111, 'target_region': 'West'}, {'account_name': '__none__', 'days_since_engage': 273, 'deal_stage': 'Engaging', 'expected_impact': "Reduce Summer Sewald's open load by one and move a high-attention opportunity to Celia Rouche within West.", 'opportunity_id': 'D5VY17OP', 'product_name': 'GTX Pro', 'reason': 'Summer Sewald is carrying 124 open opportunities in West; this opportunity has been open 273 days with risk score 0.94.', 'risk_score': 0.94, 'sales_agent_name': 'Kami Bicknell', 'source_manager': 'Summer Sewald', 'source_open_load': 124, 'source_region': 'West', 'target_manager': 'Celia Rouche', 'target_open_load': 111, 'target_region': 'West'}, {'account_name': '__none__', 'days_since_engage': 273, 'deal_stage': 'Engaging', 'expected_impact': "Reduce Summer Sewald's open load by one and move a high-attention opportunity to Celia Rouche within West.", 'opportunity_id': 'DQ7GS2BN', 'product_name': 'GTX Plus Pro', 'reason': 'Summer Sewald is carrying 124 open opportunities in West; this opportunity has been open 273 days with risk score 0.94.', 'risk_score': 0.94, 'sales_agent_name': 'James Ascencio', 'source_manager': 'Summer Sewald', 'source_open_load': 124, 'source_region': 'West', 'target_manager': 'Celia Rouche', 'target_open_load': 111, 'target_region': 'West'}, {'account_name': '__none__', 'days_since_engage': 271, 'deal_stage': 'Engaging', 'expected_impact': "Reduce Summer Sewald's open load by one and move a high-attention opportunity to Celia Rouche within West.", 'opportunity_id': 'D62905BC', 'product_name': 'GTX Plus Pro', 'reason': 'Summer Sewald is carrying 124 open opportunities in West; this opportunity has been open 271 days with risk score 0.94.', 'risk_score': 0.94, 'sales_agent_name': 'Maureen Marcano', 'source_manager': 'Summer Sewald', 'source_open_load': 124, 'source_region': 'West', 'target_manager': 'Celia Rouche', 'target_open_load': 111, 'target_region': 'West'}, {'account_name': '__none__', 'days_since_engage': 270, 'deal_stage': 'Engaging', 'expected_impact': "Reduce Summer Sewald's open load by one and move a high-attention opportunity to Celia Rouche within West.", 'opportunity_id': 'PNO7D8PD', 'product_name': 'GTX Basic', 'reason': 'Summer Sewald is carrying 124 open opportunities in West; this opportunity has been open 270 days with risk score 0.94.', 'risk_score': 0.94, 'sales_agent_name': 'Zane Levy', 'source_manager': 'Summer Sewald', 'source_open_load': 124, 'source_region': 'West', 'target_manager': 'Celia Rouche', 'target_open_load': 111, 'target_region': 'West'}], 'requires_approval': True, 'selection_basis': 'manager_capacity', 'summary': {'proposed_reassignment_count': 5, 'source_managers': ['Summer Sewald'], 'target_managers': ['Celia Rouche']}, 'visibility': {'financial_values': 'not_used_in_preview'}}, 'requested_at': '2026-04-14T05:53:23.592994+00:00', 'requested_by': {'actor_id': 'rev_ops_manager', 'email': 'human:priya.shah@example.com', 'role': 'rev_ops_manager'}, 'required_role': 'sales_leader', 'status': 'approved'}}}, 'assertion_errors': []}`

### phase6-sales-analyst-reassignment-denied [PASS]

- Category: `reassignment-preview`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prepare a reassignment plan for overloaded managers in 2017-Q2.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_reassignment_plan`
- Expected capability: `gtm.prepare_reassignment_plan`
- Actual capability: `gtm.prepare_reassignment_plan`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'pipeline', 'capability': 'gtm.prepare_reassignment_plan', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.prepare_reassignment_plan', 'success': False, 'failure_type': 'denied', 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase6-account-manager-west-reassignment-restricted [PASS]

- Category: `reassignment-preview`
- Actor: `account_manager_east`

#### Turn 1

- Question: `Prepare a reassignment plan for the West region in 2017-Q2.`
- Expected outcome: `restricted`
- Actual outcome: `restricted`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prepare_reassignment_plan`
- Expected capability: `gtm.prepare_reassignment_plan`
- Actual capability: `gtm.prepare_reassignment_plan`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'account_manager_east', 'service': 'pipeline', 'capability': 'gtm.prepare_reassignment_plan', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.prepare_reassignment_plan', 'success': False, 'failure_type': 'restricted', 'root_principal': 'human:maya.chen@example.com|actor_id=account_manager_east|display_name=Maya Chen|role=account_manager|pipeline_scope=East|financial_access=full|enrichment_access=bounded|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`
