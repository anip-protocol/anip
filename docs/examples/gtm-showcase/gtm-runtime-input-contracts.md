# GTM Runtime Input Contracts

Developer-owned runtime input contract evidence for the GTM showcase. These
tables define the implementation-facing input surface that Studio should use
when generating the ANIP contract. The PM/business documents describe the
business behavior; this document declares concrete inputs, resolution posture,
and catalog references.

## Capability Runtime Governance

| capability_id | side_effect_level | operation_type | grant_policy | produces | does_not_produce | summary |
| --- | --- | --- | --- | --- | --- | --- |
| gtm.pipeline_summary | read | read |  | content.summary | raw_data_export | Return bounded pipeline health evidence without exporting raw rows. |
| gtm.pipeline_forecast_summary | read | read |  | content.summary | raw_data_export | Return bounded forecast evidence without exporting raw rows. |
| gtm.stage_bottleneck_summary | read | read |  | content.summary | raw_data_export | Return bounded bottleneck evidence without exporting raw rows. |
| gtm.sales_team_performance_summary | read | read |  | content.summary | raw_data_export | Return bounded team performance evidence without exporting raw rows. |
| gtm.product_pipeline_summary | read | read |  | content.summary | raw_data_export | Return bounded product pipeline evidence without exporting raw rows. |
| gtm.stalled_opportunity_review | read | read |  | content.summary | raw_data_export | Return bounded stalled opportunity evidence without exporting raw rows. |
| gtm.account_risk_summary | read | read |  | content.summary | raw_data_export | Return bounded account risk evidence without exporting raw rows. |
| gtm.prepare_followup_tasks | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.summary | approval.execute, raw_data_export | Prepare follow-up task preview and stop at approval. |
| gtm.prepare_reassignment_plan | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.summary | approval.execute, raw_data_export | Prepare reassignment preview and stop at approval. |
| gtm.account_enrichment_summary | read | read |  | content.summary | raw_data_export | Return bounded enrichment context without exporting raw rows. |
| gtm.lookalike_accounts | read | read |  | content.summary | raw_data_export | Return bounded lookalike account evidence without exporting raw rows. |
| gtm.at_risk_account_enrichment_summary | read | read |  | content.summary | raw_data_export | Compose at-risk account selection with bounded enrichment context. |
| gtm.score_leads | read | read |  | content.summary, content.recommendation | raw_model_features, raw_data_export | Score a bounded lead cohort with explainable rationale without exposing raw model features. |
| gtm.prioritize_accounts | read | read |  | content.summary, content.recommendation | raw_model_features, raw_data_export | Prioritize a bounded account cohort with explainable rationale without exposing raw model features. |
| gtm.route_leads | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.summary | approval.execute, raw_model_features, raw_data_export | Prepare routing preview and stop at approval. |
| gtm.draft_outreach_message | read | read |  | content.draft | external_dispatch, system.mutation, raw_data_export | Draft outreach content without sending messages, changing backend state, or exporting raw source content. |
| gtm.suggest_followup_content | read | read |  | content.draft | external_dispatch, system.mutation, raw_data_export | Suggest follow-up content without sending messages, changing backend state, or exporting raw source content. |
| gtm.objection_response_variants | read | read |  | content.draft | external_dispatch, system.mutation, raw_data_export | Draft objection response variants without sending messages, changing backend state, or exporting raw source content. |
| gtm.bottleneck_account_outreach_draft | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.draft | external_dispatch, system.mutation, approval.execute, raw_data_export | Select or accept a bounded bottleneck target, draft outreach, and stop at approval without sending or changing backend state. |
| gtm.prioritized_outreach_draft | read | read |  | content.draft | external_dispatch, system.mutation, approval.execute, raw_data_export | Prioritize a bounded account cohort and produce draft outreach content only without sending or changing backend state. |
| gtm.at_risk_followup_preparation | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.summary | approval.execute, raw_data_export | Compose at-risk account selection with follow-up preparation and stop at approval. |
| gtm.at_risk_reassignment_preparation | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.summary | approval.execute, raw_data_export | Compose at-risk account selection with reassignment preparation and stop at approval. |
| gtm.prioritized_routing_preparation | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation, content.summary | approval.execute, raw_model_features, raw_data_export | Compose account prioritization with routing preparation and stop at approval. |

## Capability: gtm.pipeline_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| detail_level | string | no |  | no | closed_values | use_default | clarify | clarify | summary | summary, stage_breakdown |  | Summary depth |  |

## Capability: gtm.pipeline_forecast_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| forecast_mode | string | no |  | no | closed_values | use_default | clarify | clarify | risk_adjusted | risk_adjusted, likely, best_case |  | Forecast mode |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum contributing accounts or opportunities |  |

## Capability: gtm.stage_bottleneck_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| slice_by | string | no |  | no | closed_values | use_default | clarify | clarify | regional_office | regional_office, manager_name, product_name |  | Bottleneck slice |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum bottleneck rows |  |

## Capability: gtm.sales_team_performance_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| slice_by | string | no |  | no | closed_values | use_default | clarify | clarify | manager_name | manager_name, regional_office |  | Team performance slice |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum team rows |  |

## Capability: gtm.product_pipeline_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| product_scope | string | no | entity_reference | yes | backend_resolved | omit | clarify | clarify |  |  | gtm.product_catalog | Specific product to focus on |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum product rows |  |

## Capability: gtm.stalled_opportunity_review

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| min_days_open | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Minimum days open |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum opportunities |  |

## Capability: gtm.account_risk_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| ranking_basis | string | yes |  | no | closed_values | use_default | clarify | clarify | risk_score | risk_score |  | Risk ranking basis |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts |  |

## Capability: gtm.prepare_followup_tasks

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| ranking_basis | string | yes |  | no | closed_values | use_default | clarify | clarify | risk_score | risk_score |  | Risk ranking basis |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts to include |  |

## Capability: gtm.prepare_reassignment_plan

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| selection_basis | string | no |  | no | closed_values | use_default | clarify | clarify | manager_capacity | manager_capacity, stalled_risk_mix |  | Reassignment selection basis |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum reassignment candidates |  |

## Capability: gtm.account_enrichment_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| account_names | string | yes | entity_reference | yes | backend_resolved | clarify | clarify | clarify |  |  | gtm.account_catalog | Comma-separated account names | Ask which accounts to summarize. |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts to summarize |  |

## Capability: gtm.lookalike_accounts

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reference_account | string | yes | entity_reference | yes | backend_resolved | clarify | clarify | clarify |  |  | gtm.account_catalog | Reference account name | Ask which reference account to use. |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum lookalike accounts |  |

## Capability: gtm.at_risk_account_enrichment_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| ranking_basis | string | no |  | no | closed_values | use_default | clarify | clarify | risk_score | risk_score |  | Risk ranking basis |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts to enrich |  |

## Capability: gtm.score_leads

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify |  | inbound_last_week, webinar_q2 | gtm.cohort_catalog | Cohort reference; map inbound leads or last week inbound leads to inbound_last_week | Ask which lead cohort to score. |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum leads |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Actor-safe ownership scope |  |

## Capability: gtm.prioritize_accounts

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify |  | expansion_candidates_q2, at_risk_q2 | gtm.cohort_catalog | Account cohort; map expansion candidates to expansion_candidates_q2 and at risk q2 to at_risk_q2 | Ask which account cohort to prioritize. |
| ranking_basis | string | no |  | no | closed_values | use_default | clarify | clarify | deal_likelihood | deal_likelihood |  | Priority ranking basis |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Actor-safe ownership scope |  |

## Capability: gtm.route_leads

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify |  | inbound_last_week, webinar_q2 | gtm.cohort_catalog | Lead cohort; map inbound leads or last week inbound leads to inbound_last_week | Ask which lead cohort to route. |
| target_queue | string | no |  | no | closed_values | use_default | clarify | clarify | sales | sales, sdr |  | Destination queue or team |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Actor-safe ownership scope |  |

## Capability: gtm.draft_outreach_message

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_ref | string | yes | entity_reference | yes | backend_resolved | clarify | clarify | clarify |  |  | gtm.account_or_lead_catalog | Lead or account reference | Ask which lead or account the draft should target. |
| objective | string | yes |  | no | closed_values | use_default | clarify | clarify | first_touch | first_touch, follow_up, revive_stalled |  | Message objective |  |
| channel | string | no |  | no | closed_values | use_default | clarify | clarify | email | email, linkedin, call_follow_up |  | Requested outreach channel |  |
| persona | string | no | audience_reference | yes | explicit_only | omit | clarify | clarify |  |  |  | Target persona or audience |  |

## Capability: gtm.suggest_followup_content

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_ref | string | yes | entity_reference | yes | backend_resolved | clarify | clarify | clarify |  |  | gtm.account_or_lead_catalog | Lead or account reference | Ask which lead or account the follow-up should target. |
| variant_count | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum variants |  |
| persona | string | no | audience_reference | yes | explicit_only | omit | clarify | clarify |  |  |  | Target persona or audience |  |

## Capability: gtm.objection_response_variants

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| objection_theme | string | yes |  | no | closed_values | clarify | clarify | clarify |  | pricing, competitor, implementation_risk |  | Named objection theme | Ask which objection theme to address. |
| target_ref | string | no | entity_reference | yes | backend_resolved | omit | clarify | clarify |  |  | gtm.account_or_lead_catalog | Optional GTM target reference |  |
| persona | string | no | audience_reference | yes | explicit_only | omit | clarify | clarify |  |  |  | Target persona or audience |  |

## Capability: gtm.bottleneck_account_outreach_draft

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 | Ask which quarter to use for bottleneck-based outreach drafting. |
| target_ref | string | no | entity_reference | yes | backend_resolved | omit | clarify | clarify |  |  | gtm.account_catalog | Optional explicit account selected from the bottleneck review; omit when the request asks the provider to select the top candidate before the approval boundary. | Ask for a specific account only when the request is a direct draft request rather than a bottleneck-derived provider selection. |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| objective | string | no |  | no | closed_values | use_default | clarify | clarify | first_touch | first_touch, follow_up, revive_stalled |  | Message objective |  |
| channel | string | no |  | no | closed_values | use_default | clarify | clarify | email | email, linkedin, call_follow_up |  | Requested outreach channel |  |
| persona | string | no | audience_reference | yes | explicit_only | omit | clarify | clarify |  |  |  | Target persona or audience |  |

## Capability: gtm.prioritized_outreach_draft

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify |  | expansion_candidates_q2, at_risk_q2 | gtm.cohort_catalog | Account cohort to prioritize | Ask which account cohort to use. |
| ranking_basis | string | no |  | no | closed_values | use_default | clarify | clarify | deal_likelihood | deal_likelihood |  | Priority ranking basis |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts before drafting |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| objective | string | no |  | no | closed_values | use_default | clarify | clarify | first_touch | first_touch, follow_up, revive_stalled |  | Message objective |  |
| channel | string | no |  | no | closed_values | use_default | clarify | clarify | email | email, linkedin, call_follow_up |  | Requested outreach channel |  |
| persona | string | no | audience_reference | yes | explicit_only | omit | clarify | clarify |  |  |  | Target persona or audience |  |

## Capability: gtm.at_risk_followup_preparation

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| ranking_basis | string | yes |  | no | closed_values | use_default | clarify | clarify | risk_score | risk_score |  | Risk ranking basis |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts |  |

## Capability: gtm.at_risk_reassignment_preparation

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify |  |  |  | Quarter label like 2017-Q2 |  |
| ranking_basis | string | yes |  | no | closed_values | use_default | clarify | clarify | risk_score | risk_score |  | Risk ranking basis |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Regional office, team, owner, or company-wide scope |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts |  |

## Capability: gtm.prioritized_routing_preparation

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify |  | expansion_candidates_q2, at_risk_q2 | gtm.cohort_catalog | Account cohort; map expansion candidates to expansion_candidates_q2 and at risk q2 to at_risk_q2 | Ask which cohort to use. |
| ranking_basis | string | no |  | no | closed_values | use_default | clarify | clarify | deal_likelihood | deal_likelihood |  | Priority ranking basis |  |
| limit | integer | no | quantity_limit | no | explicit_only | omit | clarify | clarify |  |  |  | Maximum accounts |  |
| owner_scope | string | no | scope_reference | no | actor_policy_or_explicit | use_actor_scope | clarify | clarify |  |  |  | Actor-safe ownership scope |  |

## Reviewed Derived Target Boundary

`gtm.bottleneck_account_outreach_draft` is reviewed as service-owned derived
target behavior. When `target_ref` is omitted in a bottleneck-derived request,
the outreach service may select the bounded top candidate from the bottleneck
review context and return `approval_required`. Direct draft capabilities such
as `gtm.draft_outreach_message` and `gtm.suggest_followup_content` still require
an explicit `target_ref` and must clarify when it is missing.
