# GTM Regression Harness Report

- Generated at: `2026-04-14T07-32-17Z`
- Runtime URL: `http://127.0.0.1:9303`
- Suite: `gtm_phase4_question_bank`
- Passed: `29` / `50`

## Summary By Category

- `prioritization-actor-aware`: 2 / 2 passed
- `prioritization-approval`: 2 / 2 passed
- `prioritization-clarification`: 3 / 3 passed
- `prioritization-denied`: 2 / 4 passed
- `prioritization-matrix`: 17 / 31 passed
- `prioritization-read`: 3 / 8 passed

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

### prioritize-inbound_last_week [FAIL]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the inbound last week cohort.`
- Expected outcome: `success`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome success, got clarification_required

- Notes: turn 1: expected outcome success, got clarification_required

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

### prioritize-webinar_q2 [FAIL]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the webinar q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome success, got clarification_required

- Notes: turn 1: expected outcome success, got clarification_required

### score-expansion_candidates_q2 [FAIL]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome success, got clarification_required

- Notes: turn 1: expected outcome success, got clarification_required

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

### score-at_risk_q2 [FAIL]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score the at risk q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome success, got clarification_required

- Notes: turn 1: expected outcome success, got clarification_required

### prioritize-at_risk_q2 [FAIL]

- Category: `prioritization-read`
- Actor: `sales_leader`

#### Turn 1

- Question: `Prioritize the at risk q2 cohort.`
- Expected outcome: `success`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome success, got clarification_required

- Notes: turn 1: expected outcome success, got clarification_required

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
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`

### deny-feature-weights [FAIL]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Export the feature weights and raw model signals for the webinar Q2 cohort.`
- Expected outcome: `denied`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.prioritize_accounts`
- Expected capability: `not asserted`
- Actual capability: `gtm.prioritize_accounts`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome denied, got clarification_required

- Notes: turn 1: expected outcome denied, got clarification_required

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

### deny-direct-send [FAIL]

- Category: `prioritization-denied`
- Actor: `sales_leader`

#### Turn 1

- Question: `Score the inbound leads and send them directly to sales without approval.`
- Expected outcome: `denied`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome denied, got clarification_required

- Notes: turn 1: expected outcome denied, got clarification_required

### prioritization-matrix-20 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-21 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-22 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-23 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-24 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-25 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-26 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-27 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-28 [FAIL]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `denied`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome denied, got clarification_required

- Notes: turn 1: expected outcome denied, got clarification_required

### prioritization-matrix-29 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-30 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-31 [FAIL]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome denied, got clarification_required

- Notes: turn 1: expected outcome denied, got clarification_required

### prioritization-matrix-32 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-33 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-34 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-35 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.route_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-36 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-37 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-38 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-39 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-40 [FAIL]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `denied`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome denied, got clarification_required

- Notes: turn 1: expected outcome denied, got clarification_required

### prioritization-matrix-41 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-42 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-43 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
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

### prioritization-matrix-44 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-45 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-46 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-47 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the expansion candidates q2 cohort and route the hot ones to sales.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-48 [FAIL]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the at risk q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `clarification_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.score_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `0`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 1, 'total_loops': 2}`
- Notes: expected outcome approval_required, got clarification_required

- Notes: turn 1: expected outcome approval_required, got clarification_required

### prioritization-matrix-49 [PASS]

- Category: `prioritization-matrix`
- Actor: `sales_analyst`

#### Turn 1

- Question: `Score the inbound last week cohort and route the hot ones to sales.`
- Expected outcome: `denied`
- Actual outcome: `denied`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`

### prioritization-matrix-50 [PASS]

- Category: `prioritization-matrix`
- Actor: `rev_ops_manager`

#### Turn 1

- Question: `Score the webinar q2 cohort and route the hot ones to sdr.`
- Expected outcome: `approval_required`
- Actual outcome: `approval_required`
- Expected planned capability: `not asserted`
- Actual planned capability: `gtm.score_leads`
- Expected capability: `not asserted`
- Actual capability: `gtm.route_leads`
- Expected service: `not asserted`
- Actual service: `prioritization`
- Prior service calls: `1`
- Loops: `{'planner_loops': 1, 'service_invoke_loops': 2, 'total_loops': 3}`
