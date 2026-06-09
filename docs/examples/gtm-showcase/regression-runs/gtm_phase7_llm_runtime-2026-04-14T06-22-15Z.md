# GTM Regression Harness Report

- Generated at: `2026-04-14T06-22-15Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase7_llm_runtime`
- Passed: `4` / `4`

## Summary By Category

- `compound-actor-aware`: 1 / 1 passed
- `compound-approval`: 2 / 2 passed
- `compound-read`: 1 / 1 passed

## Cases

### phase7-prioritize-enrich-draft-compound [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.prioritize_accounts`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `gtm.draft_outreach_message`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`
- Data check `compound_prioritize_enrich_draft_expansion_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'outreach', 'capability': 'gtm.draft_outreach_message', 'min_entries': 1, 'actual_entries': 20, 'latest_entry': {'capability': 'gtm.draft_outreach_message', 'success': True, 'failure_type': None, 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase7-forecast-followup-compound-approval [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `gtm.pipeline_forecast_summary`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.prepare_followup_tasks`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`
- Data check `compound_forecast_followup_top3_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'rev_ops_manager', 'service': 'pipeline', 'capability': 'gtm.prepare_followup_tasks', 'min_entries': 1, 'actual_entries': 4, 'latest_entry': {'capability': 'gtm.prepare_followup_tasks', 'success': False, 'failure_type': 'approval_required', 'root_principal': 'human:priya.shah@example.com|actor_id=rev_ops_manager|display_name=Priya Shah|role=rev_ops_manager|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

- Approval check: `PASS`
- Approval details: `{'approval_request_id': 'apr_8e425b68d159', 'approver_actor_id': 'sales_leader', 'pending_visible': True, 'approved_visible': True, 'approval_payload': {'actor_id': 'sales_leader', 'approval_request_id': 'apr_8e425b68d159', 'service': 'pipeline', 'result': {'approval': {'approval_request_id': 'apr_8e425b68d159', 'approved_at': '2026-04-14T06:22:11.783723+00:00', 'approved_by': {'actor_id': 'sales_leader', 'role': 'sales_leader', 'email': 'human:alex.king@example.com'}, 'capability': 'gtm.prepare_followup_tasks', 'preview': {'owner_scope': 'company', 'quarter': '2017-Q2', 'ranking_basis': 'risk_score', 'requires_approval': True, 'tasks': [{'account_name': 'Betasoloin', 'reason': 'Average risk score 0.94 with 2 open opportunities and max age 246 days.', 'recommended_owner': 'Hayden Neloms', 'regional_office': 'West', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}, {'account_name': 'Betasoloin', 'reason': 'Average risk score 0.94 with 3 open opportunities and max age 256 days.', 'recommended_owner': 'Corliss Cosme', 'regional_office': 'East', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}, {'account_name': 'Condax', 'reason': 'Average risk score 0.94 with 2 open opportunities and max age 230 days.', 'recommended_owner': 'Cassey Cress', 'regional_office': 'East', 'suggested_due_in_days': 3, 'task_type': 'risk_review_followup'}]}, 'requested_at': '2026-04-14T06:22:11.507399+00:00', 'requested_by': {'actor_id': 'rev_ops_manager', 'email': 'human:priya.shah@example.com', 'role': 'rev_ops_manager'}, 'required_role': 'sales_leader', 'status': 'approved'}}}, 'assertion_errors': []}`

### phase7-forecast-followup-compound-analyst-denied [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `gtm.pipeline_forecast_summary`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `gtm.prepare_followup_tasks`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `pipeline`
- Actual service: `pipeline`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`
- Data check `compound_forecast_followup_sales_analyst_q2`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'pipeline', 'capability': 'gtm.prepare_followup_tasks', 'min_entries': 1, 'actual_entries': 2, 'latest_entry': {'capability': 'gtm.prepare_followup_tasks', 'success': False, 'failure_type': 'denied', 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase7-score-route-compound-approval-stop [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score inbound leads from last week, route the hot ones to sales, and draft a first-touch email for the highest-priority account.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `gtm.score_leads`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `gtm.route_leads`
- Actual capability: `gtm.route_leads`
- Expected service: `prioritization`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`
- Data check `compound_score_route_inbound_approval`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'rev_ops_manager', 'service': 'prioritization', 'capability': 'gtm.route_leads', 'min_entries': 1, 'actual_entries': 11, 'latest_entry': {'capability': 'gtm.route_leads', 'success': False, 'failure_type': 'approval_required', 'root_principal': 'human:priya.shah@example.com|actor_id=rev_ops_manager|display_name=Priya Shah|role=rev_ops_manager|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=false|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=false|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

- Approval check: `PASS`
- Approval details: `{'approval_request_id': 'apr_2a4ad825a88a', 'approver_actor_id': 'sales_leader', 'pending_visible': True, 'approved_visible': True, 'approval_payload': {'actor_id': 'sales_leader', 'approval_request_id': 'apr_2a4ad825a88a', 'service': 'prioritization', 'result': {'approval': {'approval_request_id': 'apr_2a4ad825a88a', 'approved_at': '2026-04-14T06:22:15.797807+00:00', 'approved_by': {'actor_id': 'sales_leader', 'role': 'sales_leader', 'email': 'human:alex.king@example.com'}, 'capability': 'gtm.route_leads', 'preview': {'cohort_ref': 'inbound_last_week', 'dry_run': True, 'owner_scope': 'company', 'preview': [{'account_name': 'Acme Corporation', 'lead_id': 'lead_1001', 'owner_scope': 'East', 'priority_band': 'hot', 'priority_score': 94, 'rationale': 'High intent, enterprise ICP fit, and recent demo request.', 'recommended_queue': 'sales'}, {'account_name': 'Codehow', 'lead_id': 'lead_1002', 'owner_scope': 'East', 'priority_band': 'hot', 'priority_score': 91, 'rationale': 'Repeat product-page engagement and strong ICP fit.', 'recommended_queue': 'sales'}, {'account_name': 'Condax', 'lead_id': 'lead_1003', 'owner_scope': 'West', 'priority_band': 'hot', 'priority_score': 88, 'rationale': 'High-value account with strong buying signals.', 'recommended_queue': 'sales'}, {'account_name': 'Dalttechnology', 'lead_id': 'lead_1004', 'owner_scope': 'Central', 'priority_band': 'warm', 'priority_score': 84, 'rationale': 'Good engagement and healthy ICP alignment.', 'recommended_queue': 'sales'}], 'target_queue': 'sales'}, 'requested_at': '2026-04-14T06:22:15.769345+00:00', 'requested_by': {'actor_id': 'rev_ops_manager', 'email': 'human:priya.shah@example.com', 'role': 'rev_ops_manager'}, 'required_role': 'sales_leader', 'status': 'approved'}}}, 'assertion_errors': []}`
