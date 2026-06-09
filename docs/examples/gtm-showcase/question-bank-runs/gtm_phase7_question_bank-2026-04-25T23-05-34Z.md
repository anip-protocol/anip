# GTM Regression Harness Report

- Generated at: `2026-04-25T23-05-34Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase7_question_bank`
- Passed: `50` / `50`

## Summary By Category

- `compound-actor-aware`: 9 / 9 passed
- `compound-approval`: 17 / 17 passed
- `compound-read`: 23 / 23 passed
- `compound-safe-stop`: 1 / 1 passed

## Cases

### compound-prioritize-enrich-draft-email [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### compound-prioritize-enrich-draft-linkedin [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### compound-prioritize-enrich-draft-followup [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a follow-up email for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### compound-forecast-followup-company [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### compound-forecast-followup-company-analyst [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.pipeline_forecast_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.prepare_followup_tasks`
- Expected service: `not asserted`
- Actual service: `pipeline`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### compound-score-route-sales [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score inbound leads from last week, route the hot ones to sales, and draft a first-touch email for the highest-priority account.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### compound-score-route-sdr [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to SDR.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### compound-route-sales-analyst [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### compound-bottleneck-enrich-east [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### compound-bottleneck-followup-east [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### compound-bottleneck-draft-safe-stop [PASS]

- Category: `compound-safe-stop`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, enrich those accounts, and draft a first-touch email for the top one.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.stage_bottleneck_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `3`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 4, 'total_loops': 5}`

### compound-forecast-followup-east [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the East region.`
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

### compound-forecast-followup-east-analyst [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the East region.`
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

### compound-prioritize-atrisk-enrich [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the at-risk accounts in 2017-Q2 and enrich the top 3 accounts.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-15 [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-16 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-17 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the West region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### phase7-matrix-18 [PASS]

- Category: `compound-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-19 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-20 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the West region.`
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

### phase7-matrix-21 [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-22 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-23 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the West region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### phase7-matrix-24 [PASS]

- Category: `compound-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-25 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-26 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the West region.`
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

### phase7-matrix-27 [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-28 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-29 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the West region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### phase7-matrix-30 [PASS]

- Category: `compound-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-31 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-32 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the West region.`
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

### phase7-matrix-33 [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-34 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-35 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the West region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### phase7-matrix-36 [PASS]

- Category: `compound-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-37 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-38 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the West region.`
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

### phase7-matrix-39 [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-40 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-41 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the West region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### phase7-matrix-42 [PASS]

- Category: `compound-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-43 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-44 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the West region.`
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

### phase7-matrix-45 [PASS]

- Category: `compound-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score inbound leads from last week and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-46 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.at_risk_account_enrichment_summary`
- Expected capability: `not asserted`
- Actual capability: `gtm.at_risk_account_enrichment_summary`
- Expected service: `not asserted`
- Actual service: `enrichment`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### phase7-matrix-47 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `For 2017-Q2 in the West region, show the biggest bottlenecks, identify the top 3 at-risk accounts contributing to them, and prepare follow-up task previews for them.`
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

### phase7-matrix-48 [PASS]

- Category: `compound-read`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a LinkedIn first-touch for the highest-priority account.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-49 [PASS]

- Category: `compound-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates in 2017-Q2, enrich the top 3 accounts, and draft a first-touch email for the highest-priority account in the East region.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.draft_outreach_message`
- Expected service: `not asserted`
- Actual service: `outreach`
- Prior service calls: `2`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 3, 'total_loops': 4}`

### phase7-matrix-50 [PASS]

- Category: `compound-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Show the risk-adjusted forecast for 2017-Q2 and prepare follow-up task previews for the top 3 at-risk accounts in the West region.`
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
