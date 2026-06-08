# GTM Regression Harness Report

- Generated at: `2026-04-25T22-59-47Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase4_question_bank`
- Passed: `50` / `50`

## Summary By Category

- `prioritization-actor-aware`: 2 / 2 passed
- `prioritization-approval`: 2 / 2 passed
- `prioritization-clarification`: 3 / 3 passed
- `prioritization-denied`: 4 / 4 passed
- `prioritization-matrix`: 35 / 35 passed
- `prioritization-read`: 4 / 4 passed

## Cases

### score-inbound_last_week [PASS]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score the inbound last week cohort.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### score-webinar_q2 [PASS]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score the webinar q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### prioritize-expansion_candidates_q2 [PASS]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the expansion candidates q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### prioritize-at_risk_q2 [PASS]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the at risk q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `success`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### route-inbound-sales-revops [PASS]

- Category: `prioritization-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Route the inbound leads from last week to SALES.`
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

### route-inbound-sales-analyst [PASS]

- Category: `prioritization-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Route the inbound leads from last week to SALES.`
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

### route-inbound-sdr-revops [PASS]

- Category: `prioritization-approval`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Route the inbound leads from last week to SDR.`
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

### route-inbound-sdr-analyst [PASS]

- Category: `prioritization-actor-aware`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Route the inbound leads from last week to SDR.`
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

### clarify-score-missing-cohort [PASS]

- Category: `prioritization-clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score these leads.`
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

### clarify-prioritize-missing-cohort [PASS]

- Category: `prioritization-clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize these accounts.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### clarify-route-missing-cohort [PASS]

- Category: `prioritization-clarification`
- Actor: `sales_leader`

#### Turn 1

- Question: `Route the hot ones to sales.`
- Expected outcome: `clarification_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### deny-raw-model-features [PASS]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Show me the raw model features for the inbound leads from last week.`
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

### deny-feature-weights [PASS]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Export the feature weights and raw model signals for the webinar Q2 cohort.`
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

### deny-routing-with-export [PASS]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Route the hot ones to sales and include the raw underlying model payload.`
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

### deny-direct-send [PASS]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score the inbound leads and send them directly to sales without approval.`
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

### prioritization-matrix-16 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-17 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-18 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-19 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-20 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-21 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-22 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-23 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-24 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-25 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-26 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-27 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-28 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-29 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-30 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-31 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-32 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-33 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-34 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-35 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-36 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-37 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-38 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-39 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-40 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-41 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-42 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-43 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-44 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-45 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-46 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-47 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-48 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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

### prioritization-matrix-49 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
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

### prioritization-matrix-50 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
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
