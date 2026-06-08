# GTM Regression Harness Report

- Generated at: `2026-04-14T03-32-10Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase5_llm_runtime`
- Passed: `8` / `8`

## Summary By Category

- `outreach-actor-aware`: 2 / 2 passed
- `outreach-clarification`: 1 / 1 passed
- `outreach-denied`: 2 / 2 passed
- `outreach-draft`: 3 / 3 passed

## Cases

### phase5-draft-condax-first-touch [PASS]

- Category: `outreach-draft`
- Actor: `sales_leader`

#### Turn 1

- Question: `Draft a first-touch email for Condax based on its current GTM context.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.draft_outreach_message`
- Expected capability: `gtm.draft_outreach_message`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `draft_outreach_condax_first_touch`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'outreach', 'capability': 'gtm.draft_outreach_message', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.draft_outreach_message', 'success': True, 'failure_type': None, 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase5-clarify-target-followup [PASS]

- Category: `outreach-clarification`
- Actor: `sales_leader`
- Turns: `2`

#### Turn 1

- Question: `Draft a first-touch email for this prospect.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.draft_outreach_message`
- Expected capability: `gtm.draft_outreach_message`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

#### Turn 2

- Question: `Use Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `gtm.draft_outreach_message`
- Actual planned capability: `gtm.draft_outreach_message`
- Expected capability: `gtm.draft_outreach_message`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `draft_outreach_condax_first_touch`: `PASS`

### phase5-followup-variants-condax [PASS]

- Category: `outreach-draft`
- Actor: `sales_leader`

#### Turn 1

- Question: `Generate three follow-up variants for Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.suggest_followup_content`
- Expected capability: `gtm.suggest_followup_content`
- Actual capability: `gtm.suggest_followup_content`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `followup_variants_condax`: `PASS`

### phase5-sales-analyst-followup-bounded [PASS]

- Category: `outreach-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Generate three follow-up variants for Condax.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.suggest_followup_content`
- Expected capability: `gtm.suggest_followup_content`
- Actual capability: `gtm.suggest_followup_content`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `followup_variants_condax_bounded`: `PASS`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'outreach', 'capability': 'gtm.suggest_followup_content', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.suggest_followup_content', 'success': True, 'failure_type': None, 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': True, 'signature_present': True}, 'assertion_errors': []}`

### phase5-objection-variants-competitor [PASS]

- Category: `outreach-draft`
- Actor: `sales_leader`

#### Turn 1

- Question: `Suggest objection-response variants for a competitor comparison.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.objection_response_variants`
- Expected capability: `gtm.objection_response_variants`
- Actual capability: `gtm.objection_response_variants`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Data check `objection_variants_competitor`: `PASS`

### phase5-sales-analyst-objection-denied [PASS]

- Category: `outreach-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Suggest objection-response variants for a competitor comparison.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.objection_response_variants`
- Expected capability: `gtm.objection_response_variants`
- Actual capability: `gtm.objection_response_variants`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_analyst', 'service': 'outreach', 'capability': 'gtm.objection_response_variants', 'min_entries': 1, 'actual_entries': 1, 'latest_entry': {'capability': 'gtm.objection_response_variants', 'success': False, 'failure_type': 'denied', 'root_principal': 'human:jordan.lee@example.com|actor_id=sales_analyst|display_name=Jordan Lee|role=sales_analyst|pipeline_scope=company|financial_access=masked|enrichment_access=bounded|outreach_access=bounded|can_prepare_followup=false|can_approve_followup=false|can_use_lookalikes=false|can_route_leads=false|can_approve_routing=false|can_use_objection_variants=false', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase5-send-denied [PASS]

- Category: `outreach-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Send this outreach sequence now.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.draft_outreach_message`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'outreach', 'capability': None, 'min_entries': 1, 'actual_entries': 6, 'latest_entry': {'capability': 'gtm.draft_outreach_message', 'success': False, 'failure_type': 'denied', 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`

### phase5-raw-transcript-denied [PASS]

- Category: `outreach-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show me the raw sales-conversation transcripts you used to draft this message.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.draft_outreach_message`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `outreach`
- Actual service: `outreach`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

- Audit check: `PASS`
- Audit details: `{'actor_id': 'sales_leader', 'service': 'outreach', 'capability': None, 'min_entries': 1, 'actual_entries': 7, 'latest_entry': {'capability': 'gtm.draft_outreach_message', 'success': False, 'failure_type': 'denied', 'root_principal': 'human:alex.king@example.com|actor_id=sales_leader|display_name=Alex King|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true', 'storage_redacted': False, 'signature_present': True}, 'assertion_errors': []}`
