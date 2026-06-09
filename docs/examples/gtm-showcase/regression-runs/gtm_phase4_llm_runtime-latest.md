# GTM Regression Harness Report

- Generated at: `2026-04-14T05-36-54Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase4_llm_runtime`
- Passed: `6` / `6`

## Summary By Category

- `prioritization-approval`: 2 / 2 passed
- `prioritization-clarification`: 1 / 1 passed
- `prioritization-denied`: 1 / 1 passed
- `prioritization-read`: 2 / 2 passed

## Cases

### phase4-score-inbound-last-week [PASS]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score inbound leads from last week and rank the hottest 10.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `gtm.score_leads`
- Actual capability: `gtm.score_leads`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `score_leads_inbound_last_week`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'prioritization', 'capability': 'gtm.score_leads', 'min_entries': 1, 'actual_entries': 20, 'latest_entry': {'capability': 'gtm.score_leads', 'success': True, 'failure_type': None, 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase4-clarify-latest-leads-followup [PASS]

- Category: `prioritization-clarification`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Score our latest leads.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `gtm.score_leads`
- Actual capability: `gtm.score_leads`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use inbound_last_week.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.score_leads`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `gtm.score_leads`
- Actual capability: `gtm.score_leads`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `score_leads_inbound_last_week`: `PASS`

### phase4-prioritize-expansion-candidates [PASS]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `gtm.prioritize_accounts`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `prioritize_accounts_expansion_candidates_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'prioritization', 'capability': 'gtm.prioritize_accounts', 'min_entries': 1, 'actual_entries': 12, 'latest_entry': {'capability': 'gtm.prioritize_accounts', 'success': True, 'failure_type': None, 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase4-deny-raw-model-export [PASS]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show me every raw model feature and weight behind the lead scores.`
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

### phase4-route-webinar-leads-approval [PASS]

- Category: `prioritization-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Route the webinar leads to sales right now.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `gtm.route_leads`
- Actual capability: `gtm.route_leads`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `route_preview_webinar_q2_sales`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'rev_ops_manager', 'service': 'prioritization', 'capability': 'gtm.route_leads', 'min_entries': 1, 'actual_entries': 7, 'latest_entry': {'capability': 'gtm.route_leads', 'success': False, 'failure_type': 'approval_required', 'root_principal': 'human:priya.shah@example.com|actor_id=rev_ops_manager|display_name=Priya Shah|role=rev_ops_manager|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

- Approval check: `PASS`
- Approval details: `{'approval_request_id': 'apr_e043f462ee95', 'approver_actor_id': 'sales_leader', 'pending_visible': True, 'approved_visible': True, 'approval_payload': {'actor_id': 'sales_leader', 'approval_request_id': 'apr_e043f462ee95', 'service': 'prioritization', 'result': {'approval': {'approval_request_id': 'apr_e043f462ee95', 'approved_at': '2026-04-14T05:36:53.203762+00:00', 'approved_by': {'actor_id': 'sales_leader', 'role': 'sales_leader', 'email': 'human:alex.king@example.com'}, 'capability': 'gtm.route_leads', 'preview': {'cohort_ref': 'webinar_q2', 'dry_run': True, 'owner_scope': 'company', 'preview': [{'account_name': 'Finjob', 'lead_id': 'lead_2001', 'owner_scope': 'East', 'priority_band': 'hot', 'priority_score': 89, 'rationale': 'Executive webinar attendance and requested follow-up.', 'recommended_queue': 'sales'}, {'account_name': 'J-Texon', 'lead_id': 'lead_2002', 'owner_scope': 'West', 'priority_band': 'warm', 'priority_score': 81, 'rationale': 'Good engagement but smaller likely deal size.', 'recommended_queue': 'sales'}, {'account_name': 'Konex', 'lead_id': 'lead_2003', 'owner_scope': 'West', 'priority_band': 'warm', 'priority_score': 78, 'rationale': 'Moderate engagement and reasonable ICP fit.', 'recommended_queue': 'sales'}], 'target_queue': 'sales'}, 'requested_at': '2026-04-14T05:36:53.175152+00:00', 'requested_by': {'actor_id': 'rev_ops_manager', 'email': 'human:priya.shah@example.com', 'role': 'rev_ops_manager'}, 'required_role': 'sales_leader', 'status': 'approved'}}}, 'assertion_errors': []}`

### phase4-sales-analyst-routing-denied [PASS]

- Category: `prioritization-approval`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Route the webinar leads to sales right now.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `gtm.route_leads`
- Actual capability: `gtm.route_leads`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'prioritization', 'capability': 'gtm.route_leads', 'min_entries': 1, 'actual_entries': 7, 'latest_entry': {'capability': 'gtm.route_leads', 'success': False, 'failure_type': 'denied', 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`
