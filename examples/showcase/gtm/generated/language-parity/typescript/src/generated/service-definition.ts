// Generated from an exported ANIP Service Definition.
export const serviceDefinition = ({
  "artifact_type": "anip_service_definition",
  "contract_schema_version": "anip-service-definition/v1",
  "compiled_contract_identity": {
    "signature": "sha256:c8ef395f5f19361a2f86e7078b2f8cec199b346d69293f3b754380063636f4e8",
    "signature_algorithm": "sha256"
  },
  "identity": {
    "system_name": "GTM Operator Contract 20260512235040",
    "domain_name": "gtm",
    "delivery_model": "multiple_coordinated_services",
    "architecture_shape": "multi_service_estate"
  },
  "authority": {
    "approval_expectation": "not_specified"
  },
  "audit": {
    "durable_records_required": true,
    "searchable_history_required": true
  },
  "generation": {
    "protocols": [
      "anip_http"
    ],
    "layout_strategy": "monorepo",
    "selected_service_ids": [
      "gtm-pipeline-service",
      "gtm-enrichment-service",
      "gtm-prioritization-service",
      "gtm-outreach-service"
    ]
  },
  "service_topology_bindings": [
    {
      "id": "service_topology_gtm-pipeline-service",
      "service_id": "gtm-pipeline-service",
      "service_name": "Pipeline Service",
      "source_role": "governs CRM-state reads and operational previews",
      "source_capabilities": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan"
      ],
      "formalized_capability_ids": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan"
      ]
    },
    {
      "id": "service_topology_gtm-enrichment-service",
      "service_id": "gtm-enrichment-service",
      "service_name": "Enrichment Service",
      "source_role": "provides bounded account context",
      "source_capabilities": [
        "gtm.account_enrichment_summary",
        "gtm.lookalike_accounts",
        "gtm.at_risk_account_enrichment_summary"
      ],
      "formalized_capability_ids": [
        "gtm.account_enrichment_summary",
        "gtm.lookalike_accounts",
        "gtm.at_risk_account_enrichment_summary"
      ]
    },
    {
      "id": "service_topology_gtm-prioritization-service",
      "service_id": "gtm-prioritization-service",
      "service_name": "Prioritization Service",
      "source_role": "scores and ranks bounded cohorts",
      "source_capabilities": [
        "gtm.score_leads",
        "gtm.prioritize_accounts",
        "gtm.route_leads"
      ],
      "formalized_capability_ids": [
        "gtm.score_leads",
        "gtm.prioritize_accounts",
        "gtm.route_leads"
      ]
    },
    {
      "id": "service_topology_gtm-outreach-service",
      "service_id": "gtm-outreach-service",
      "service_name": "Outreach Service",
      "source_role": "drafts bounded outbound content",
      "source_capabilities": [
        "gtm.draft_outreach_message",
        "gtm.suggest_followup_content",
        "gtm.objection_response_variants",
        "gtm.bottleneck_account_outreach_draft",
        "gtm.prioritized_outreach_draft"
      ],
      "formalized_capability_ids": [
        "gtm.draft_outreach_message",
        "gtm.suggest_followup_content",
        "gtm.objection_response_variants",
        "gtm.bottleneck_account_outreach_draft",
        "gtm.prioritized_outreach_draft"
      ]
    }
  ],
  "capability_formalizations": [
    {
      "id": "contract_native:gtm.pipeline_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.pipeline_summary",
      "title": "pipeline_summary",
      "summary": "Return a bounded pipeline health summary for a quarter and optional scope.",
      "subject_kind": "quarter-scoped GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "pipeline health visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.pipeline_summary",
      "path_template": "/gtm/pipeline-summary",
      "output_shape": "gtm_pipeline_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "detail_level",
          "input_type": "string",
          "required": false,
          "summary": "summary or stage_breakdown",
          "default_value": "summary",
          "allowed_values": [
            "summary",
            "stage_breakdown"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.pipeline_forecast_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.pipeline_forecast_summary",
      "title": "pipeline_forecast_summary",
      "summary": "Return a bounded forecast summary for open pipeline with likely, best-case, and risk-adjusted views.",
      "subject_kind": "quarter-scoped GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "forecast posture visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.pipeline_forecast_summary",
      "path_template": "/gtm/pipeline-forecast-summary",
      "output_shape": "gtm_pipeline_forecast_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "forecast_mode",
          "input_type": "string",
          "required": false,
          "summary": "risk_adjusted, likely, or best_case",
          "default_value": "risk_adjusted",
          "allowed_values": [
            "risk_adjusted",
            "likely",
            "best_case"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum contributing accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.stage_bottleneck_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.stage_bottleneck_summary",
      "title": "stage_bottleneck_summary",
      "summary": "Return a bounded stage bottleneck summary for open pipeline by an allowed slice.",
      "subject_kind": "quarter-scoped GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "bottleneck visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.stage_bottleneck_summary",
      "path_template": "/gtm/stage-bottleneck-summary",
      "output_shape": "gtm_stage_bottleneck_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "slice_by",
          "input_type": "string",
          "required": false,
          "summary": "regional_office, manager_name, or product_name",
          "default_value": "regional_office",
          "allowed_values": [
            "regional_office",
            "manager_name",
            "product_name"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum bottleneck rows to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.sales_team_performance_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.sales_team_performance_summary",
      "title": "sales_team_performance_summary",
      "summary": "Return a bounded sales team performance summary for a quarter and optional scope.",
      "subject_kind": "quarter-scoped GTM leader",
      "context_type": "quarter and optional owner scope",
      "output_intent": "team performance visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.sales_team_performance_summary",
      "path_template": "/gtm/sales-team-performance-summary",
      "output_shape": "gtm_sales_team_performance_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "slice_by",
          "input_type": "string",
          "required": false,
          "summary": "manager_name or regional_office",
          "default_value": "manager_name",
          "allowed_values": [
            "manager_name",
            "regional_office"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum team rows to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.product_pipeline_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.product_pipeline_summary",
      "title": "product_pipeline_summary",
      "summary": "Return a bounded product pipeline summary for a quarter and optional scope.",
      "subject_kind": "quarter-scoped GTM leader",
      "context_type": "quarter and optional owner scope",
      "output_intent": "product pipeline visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.product_pipeline_summary",
      "path_template": "/gtm/product-pipeline-summary",
      "output_shape": "gtm_product_pipeline_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "product_scope",
          "input_type": "string",
          "required": false,
          "summary": "Specific product to focus on",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.product_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.product_catalog",
            "on_missing": "omit",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum product rows to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.stalled_opportunity_review",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.stalled_opportunity_review",
      "title": "stalled_opportunity_review",
      "summary": "Return stalled open opportunities with bounded evidence and explainable stall reasoning.",
      "subject_kind": "quarter-scoped GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "stalled opportunity visibility",
      "intent_type": "read",
      "operation_type": "review",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.stalled_opportunity_review",
      "path_template": "/gtm/stalled-opportunity-review",
      "output_shape": "gtm_stalled_opportunity_review_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "min_days_open",
          "input_type": "integer",
          "required": false,
          "summary": "Minimum days open",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum opportunities to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.account_risk_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.account_risk_summary",
      "title": "account_risk_summary",
      "summary": "Rank at-risk accounts with explicit evidence for why they need attention.",
      "subject_kind": "quarter-scoped GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "risk visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.account_risk_summary",
      "path_template": "/gtm/account-risk-summary",
      "output_shape": "gtm_account_risk_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": true,
          "summary": "Risk ranking basis",
          "default_value": "risk_score",
          "allowed_values": [
            "risk_score"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.prepare_followup_tasks",
      "kind": "atomic",
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.prepare_followup_tasks",
      "title": "prepare_followup_tasks",
      "summary": "Prepare follow-up tasks for high-risk accounts without executing downstream mutations.",
      "subject_kind": "authorized GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "operational preview",
      "intent_type": "approval_required",
      "operation_type": "preview_mutation",
      "side_effect_level": "approval_required",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "approval.execute"
        ]
      },
      "backend_operation": "system.preview_mutation",
      "path_template": "/gtm/prepare-followup-tasks",
      "output_shape": "gtm_prepare_followup_tasks_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": true,
          "summary": "Risk ranking basis",
          "default_value": "risk_score",
          "allowed_values": [
            "risk_score"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to include",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.prepare_reassignment_plan",
      "kind": "atomic",
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "contract_native",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.prepare_reassignment_plan",
      "title": "prepare_reassignment_plan",
      "summary": "Prepare a reassignment preview for overloaded pipeline coverage without executing downstream mutations.",
      "subject_kind": "authorized GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "operational preview",
      "intent_type": "approval_required",
      "operation_type": "preview_mutation",
      "side_effect_level": "approval_required",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "approval.execute"
        ]
      },
      "backend_operation": "system.preview_mutation",
      "path_template": "/gtm/prepare-reassignment-plan",
      "output_shape": "gtm_prepare_reassignment_plan_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "selection_basis",
          "input_type": "string",
          "required": false,
          "summary": "manager_capacity or stalled_risk_mix",
          "default_value": "manager_capacity",
          "allowed_values": [
            "manager_capacity",
            "stalled_risk_mix"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum reassignment candidates to include",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.account_enrichment_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-enrichment-service",
      "capability_id": "gtm.account_enrichment_summary",
      "title": "account_enrichment_summary",
      "summary": "Return bounded firmographic context and fit signals for selected accounts; raw records, full exports, underlying notes, and debug payloads are not supported.",
      "subject_kind": "account manager or revenue operator",
      "context_type": "selected account scope",
      "output_intent": "account context visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.account_enrichment_summary",
      "path_template": "/gtm/account-enrichment-summary",
      "output_shape": "gtm_account_enrichment_summary_result",
      "inputs": [
        {
          "input_name": "account_names",
          "input_type": "string",
          "required": true,
          "summary": "Comma-separated account names",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.account_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.account_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to summarize",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.lookalike_accounts",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-enrichment-service",
      "capability_id": "gtm.lookalike_accounts",
      "title": "lookalike_accounts",
      "summary": "Return bounded lookalike accounts using explainable similarity logic; raw payloads and underlying model data are not supported.",
      "subject_kind": "account manager or revenue operator",
      "context_type": "reference account",
      "output_intent": "lookalike discovery",
      "intent_type": "read",
      "operation_type": "discovery",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.lookalike_accounts",
      "path_template": "/gtm/lookalike-accounts",
      "output_shape": "gtm_lookalike_accounts_result",
      "inputs": [
        {
          "input_name": "reference_account",
          "input_type": "string",
          "required": true,
          "summary": "Reference account name",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.account_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.account_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum lookalike accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.at_risk_account_enrichment_summary",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-enrichment-service",
      "capability_id": "gtm.at_risk_account_enrichment_summary",
      "title": "at_risk_account_enrichment_summary",
      "summary": "Rank at-risk accounts and return bounded enrichment context for the selected accounts.",
      "subject_kind": "quarter-scoped GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "at-risk account visibility",
      "intent_type": "read",
      "operation_type": "summary",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.at_risk_account_enrichment_summary",
      "path_template": "/gtm/at-risk-account-enrichment-summary",
      "output_shape": "gtm_at_risk_account_enrichment_summary_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": false,
          "summary": "Risk ranking basis",
          "default_value": "risk_score",
          "allowed_values": [
            "risk_score"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to enrich",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.score_leads",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-prioritization-service",
      "capability_id": "gtm.score_leads",
      "title": "score_leads",
      "summary": "Return bounded lead scores and explainable priority bands for a named cohort.",
      "subject_kind": "rev ops manager or sales leader",
      "context_type": "cohort and optional owner scope",
      "output_intent": "lead prioritization",
      "intent_type": "read",
      "operation_type": "ranking",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary",
          "content.recommendation"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.score_leads",
      "path_template": "/gtm/score-leads",
      "output_shape": "gtm_score_leads_result",
      "inputs": [
        {
          "input_name": "cohort_ref",
          "input_type": "string",
          "required": true,
          "summary": "Cohort reference; map phrases like inbound leads or last week inbound leads to inbound_last_week",
          "default_value": "",
          "allowed_values": [
            "inbound_last_week",
            "webinar_q2"
          ],
          "semantic_type": "cohort_reference",
          "catalog_ref": "gtm.cohort_catalog",
          "resolution": {
            "mode": "closed_values",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum leads to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Actor-safe ownership scope",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.prioritize_accounts",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-prioritization-service",
      "capability_id": "gtm.prioritize_accounts",
      "title": "prioritize_accounts",
      "summary": "Rank bounded accounts or enriched cohorts by explainable GTM priority.",
      "subject_kind": "rev ops manager or sales leader",
      "context_type": "cohort and optional ownership scope",
      "output_intent": "account prioritization",
      "intent_type": "read",
      "operation_type": "ranking",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.summary",
          "content.recommendation"
        ],
        "does_not_produce": [
          "raw_data_export"
        ]
      },
      "backend_operation": "gtm.prioritize_accounts",
      "path_template": "/gtm/prioritize-accounts",
      "output_shape": "gtm_prioritize_accounts_result",
      "inputs": [
        {
          "input_name": "cohort_ref",
          "input_type": "string",
          "required": true,
          "summary": "Account cohort; map phrases like expansion candidates to expansion_candidates_q2 and at risk q2 to at_risk_q2",
          "default_value": "",
          "allowed_values": [
            "expansion_candidates_q2",
            "at_risk_q2"
          ],
          "semantic_type": "cohort_reference",
          "catalog_ref": "gtm.cohort_catalog",
          "resolution": {
            "mode": "closed_values",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": false,
          "summary": "Priority ranking basis",
          "default_value": "deal_likelihood",
          "allowed_values": [
            "deal_likelihood"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Actor-safe ownership scope",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.route_leads",
      "kind": "atomic",
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "contract_native",
      "service_id": "gtm-prioritization-service",
      "capability_id": "gtm.route_leads",
      "title": "route_leads",
      "summary": "Prepare an approval-gated routing preview for scored or hot leads in a named cohort; outreach drafting is not supported by this capability.",
      "subject_kind": "rev ops manager or sales leader",
      "context_type": "cohort and optional ownership scope",
      "output_intent": "routing preview",
      "intent_type": "approval_required",
      "operation_type": "preview_mutation",
      "side_effect_level": "approval_required",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.draft",
          "content.recommendation",
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "external_dispatch",
          "system.mutation",
          "approval.execute"
        ]
      },
      "backend_operation": "system.preview_mutation",
      "path_template": "/gtm/route-leads",
      "output_shape": "gtm_route_leads_result",
      "inputs": [
        {
          "input_name": "cohort_ref",
          "input_type": "string",
          "required": true,
          "summary": "Lead cohort; map phrases like inbound leads or last week inbound leads to inbound_last_week",
          "default_value": "",
          "allowed_values": [
            "inbound_last_week",
            "webinar_q2"
          ],
          "semantic_type": "cohort_reference",
          "catalog_ref": "gtm.cohort_catalog",
          "resolution": {
            "mode": "closed_values",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "target_queue",
          "input_type": "string",
          "required": false,
          "summary": "Destination queue or team; defaults to sales when the user asks for routing recommendations without naming a queue",
          "default_value": "sales",
          "allowed_values": [
            "sales",
            "sdr"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Actor-safe ownership scope",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.draft_outreach_message",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-outreach-service",
      "capability_id": "gtm.draft_outreach_message",
      "title": "draft_outreach_message",
      "summary": "Draft a bounded outreach message for a selected target and explicit objective; send actions and raw transcripts are not supported.",
      "subject_kind": "sales user or account manager",
      "context_type": "target and objective",
      "output_intent": "outreach drafting",
      "intent_type": "draft",
      "operation_type": "generation",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.draft"
        ],
        "does_not_produce": [
          "external_dispatch",
          "system.mutation"
        ]
      },
      "backend_operation": "gtm.draft_outreach_message",
      "path_template": "/gtm/draft-outreach-message",
      "output_shape": "gtm_draft_outreach_message_result",
      "inputs": [
        {
          "input_name": "target_ref",
          "input_type": "string",
          "required": true,
          "summary": "Lead or account reference",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.account_or_lead_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.account_or_lead_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "objective",
          "input_type": "string",
          "required": true,
          "summary": "Message objective",
          "default_value": "first_touch",
          "allowed_values": [
            "first_touch",
            "follow_up",
            "revive_stalled"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "channel",
          "input_type": "string",
          "required": false,
          "summary": "Requested outreach channel",
          "default_value": "email",
          "allowed_values": [
            "email",
            "linkedin",
            "call_follow_up"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "persona",
          "input_type": "string",
          "required": false,
          "summary": "Target persona or audience",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.suggest_followup_content",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-outreach-service",
      "capability_id": "gtm.suggest_followup_content",
      "title": "suggest_followup_content",
      "summary": "Return bounded follow-up content variants for an explicit GTM target.",
      "subject_kind": "sales user or account manager",
      "context_type": "target and persona",
      "output_intent": "follow-up drafting",
      "intent_type": "draft",
      "operation_type": "generation",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.draft",
          "content.recommendation"
        ],
        "does_not_produce": [
          "external_dispatch",
          "system.mutation"
        ]
      },
      "backend_operation": "gtm.suggest_followup_content",
      "path_template": "/gtm/suggest-followup-content",
      "output_shape": "gtm_suggest_followup_content_result",
      "inputs": [
        {
          "input_name": "target_ref",
          "input_type": "string",
          "required": true,
          "summary": "Lead or account reference",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.account_or_lead_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.account_or_lead_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "variant_count",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum variants to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        },
        {
          "input_name": "persona",
          "input_type": "string",
          "required": false,
          "summary": "Target persona or audience",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.objection_response_variants",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-outreach-service",
      "capability_id": "gtm.objection_response_variants",
      "title": "objection_response_variants",
      "summary": "Return bounded objection-response variants for a selected competitor or concern.",
      "subject_kind": "sales user or account manager",
      "context_type": "objection theme and optional target",
      "output_intent": "objection handling drafting",
      "intent_type": "draft",
      "operation_type": "generation",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.draft",
          "content.recommendation"
        ],
        "does_not_produce": [
          "external_dispatch",
          "system.mutation"
        ]
      },
      "backend_operation": "gtm.objection_response_variants",
      "path_template": "/gtm/objection-response-variants",
      "output_shape": "gtm_objection_response_variants_result",
      "inputs": [
        {
          "input_name": "objection_theme",
          "input_type": "string",
          "required": true,
          "summary": "Named objection theme. Use competitor for competitor objections.",
          "default_value": "",
          "allowed_values": [
            "pricing",
            "competitor",
            "implementation_risk"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "target_ref",
          "input_type": "string",
          "required": false,
          "summary": "Optional GTM target reference",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.account_or_lead_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.account_or_lead_catalog",
            "on_missing": "omit",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "persona",
          "input_type": "string",
          "required": false,
          "summary": "Target persona or audience",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.bottleneck_account_outreach_draft",
      "kind": "atomic",
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "contract_native",
      "service_id": "gtm-outreach-service",
      "capability_id": "gtm.bottleneck_account_outreach_draft",
      "title": "bottleneck_account_outreach_draft",
      "summary": "Draft outreach only for a specific account already selected from a bounded bottleneck or at-risk account review. Do not use this capability to choose the top or affected account from analysis; use the approval-gated follow-up preparation flow for derived-target bottleneck or at-risk requests.",
      "subject_kind": "sales user or account manager",
      "context_type": "quarter and selected account",
      "output_intent": "outreach drafting",
      "intent_type": "draft",
      "operation_type": "generation",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.draft",
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "external_dispatch",
          "system.mutation",
          "approval.execute"
        ]
      },
      "backend_operation": "gtm.bottleneck_account_outreach_draft",
      "path_template": "/gtm/bottleneck-account-outreach-draft",
      "output_shape": "gtm_bottleneck_account_outreach_draft_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "target_ref",
          "input_type": "string",
          "required": true,
          "summary": "Specific account selected from the bottleneck review",
          "default_value": "",
          "semantic_type": "entity_reference",
          "entity_reference": true,
          "catalog_ref": "gtm.account_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "gtm.account_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "objective",
          "input_type": "string",
          "required": false,
          "summary": "Message objective",
          "default_value": "first_touch",
          "allowed_values": [
            "first_touch",
            "follow_up",
            "revive_stalled"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "channel",
          "input_type": "string",
          "required": false,
          "summary": "Requested outreach channel",
          "default_value": "email",
          "allowed_values": [
            "email",
            "linkedin",
            "call_follow_up"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "persona",
          "input_type": "string",
          "required": false,
          "summary": "Target persona or audience",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "contract_native:gtm.prioritized_outreach_draft",
      "kind": "atomic",
      "source_kind": "contract_native",
      "service_id": "gtm-outreach-service",
      "capability_id": "gtm.prioritized_outreach_draft",
      "title": "prioritized_outreach_draft",
      "summary": "Prioritize a bounded account cohort, include bounded enrichment context for the top accounts, and draft one outreach message for the highest-priority account; this is for prioritization-to-enrichment-to-draft requests, not lead routing.",
      "subject_kind": "sales user or account manager",
      "context_type": "cohort and optional ownership scope",
      "output_intent": "prioritized outreach drafting",
      "intent_type": "draft",
      "operation_type": "compound_read_and_draft",
      "side_effect_level": "read_only",
      "implementation_fit": {
        "category": "custom_service_logic",
        "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
      },
      "business_effects": {
        "produces": [
          "content.draft",
          "content.recommendation"
        ],
        "does_not_produce": [
          "external_dispatch",
          "system.mutation"
        ]
      },
      "backend_operation": "gtm.prioritized_outreach_draft",
      "path_template": "/gtm/prioritized-outreach-draft",
      "output_shape": "gtm_prioritized_outreach_draft_result",
      "inputs": [
        {
          "input_name": "cohort_ref",
          "input_type": "string",
          "required": true,
          "summary": "Account cohort to prioritize, such as expansion_candidates_q2",
          "default_value": "",
          "allowed_values": [
            "expansion_candidates_q2",
            "at_risk_q2"
          ],
          "semantic_type": "cohort_reference",
          "catalog_ref": "gtm.cohort_catalog",
          "resolution": {
            "mode": "closed_values",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": false,
          "summary": "Priority ranking basis",
          "default_value": "deal_likelihood",
          "allowed_values": [
            "deal_likelihood"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to consider before drafting",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "objective",
          "input_type": "string",
          "required": false,
          "summary": "Message objective",
          "default_value": "first_touch",
          "allowed_values": [
            "first_touch",
            "follow_up",
            "revive_stalled"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "channel",
          "input_type": "string",
          "required": false,
          "summary": "Requested outreach channel",
          "default_value": "email",
          "allowed_values": [
            "email",
            "linkedin",
            "call_follow_up"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "persona",
          "input_type": "string",
          "required": false,
          "summary": "Target persona or audience",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "composition:inferred:gtm_account_risk_summary:gtm_prepare_followup_tasks",
      "kind": "composed",
      "composition": {
        "authority_boundary": "same_service",
        "steps": [
          {
            "id": "account_risk_summary",
            "capability": "gtm.account_risk_summary",
            "empty_result_source": true
          },
          {
            "id": "prepare_followup_tasks",
            "capability": "gtm.prepare_followup_tasks"
          }
        ],
        "input_mapping": {
          "account_risk_summary": {
            "limit": "$.input.limit",
            "owner_scope": "$.input.owner_scope",
            "quarter": "$.input.quarter",
            "ranking_basis": "$.input.ranking_basis"
          },
          "prepare_followup_tasks": {
            "limit": "$.input.limit",
            "owner_scope": "$.input.owner_scope",
            "quarter": "$.input.quarter",
            "ranking_basis": "$.input.ranking_basis"
          }
        },
        "output_mapping": {
          "result": "$.steps.prepare_followup_tasks.output.result"
        },
        "empty_result_policy": "return_success_no_results",
        "empty_result_output": {
          "empty": true,
          "result": null
        },
        "failure_policy": {
          "child_clarification": "propagate",
          "child_denial": "propagate",
          "child_approval_required": "propagate",
          "child_error": "fail_parent"
        },
        "audit_policy": {
          "record_child_invocations": true,
          "parent_task_lineage": true
        }
      },
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "application_integration",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.at_risk_followup_preparation",
      "title": "Gtm.At Risk Followup Preparation",
      "summary": "Compose gtm.account_risk_summary -\u003e gtm.prepare_followup_tasks when the requested business action needs derived targets before governed preparation.",
      "subject_kind": "authorized GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "operational preview",
      "intent_type": "business_action",
      "operation_type": "approval_gated",
      "side_effect_level": "approval_required",
      "implementation_fit": {
        "category": "native_anip",
        "rationale": "Represented as a declared contract-level composed business capability. Child handlers may still require service implementation."
      },
      "business_effects": {
        "produces": [
          "content.summary",
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "raw_data_export",
          "approval.execute"
        ]
      },
      "backend_operation": "gtm.at_risk_followup_preparation",
      "path_template": "/gtm/at-risk-followup-preparation",
      "output_shape": "gtm_at_risk_followup_preparation_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": true,
          "summary": "Risk ranking basis",
          "default_value": "risk_score",
          "allowed_values": [
            "risk_score"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "composition:inferred:gtm_account_risk_summary:gtm_prepare_reassignment_plan",
      "kind": "composed",
      "composition": {
        "authority_boundary": "same_service",
        "steps": [
          {
            "id": "account_risk_summary",
            "capability": "gtm.account_risk_summary",
            "empty_result_source": true
          },
          {
            "id": "prepare_reassignment_plan",
            "capability": "gtm.prepare_reassignment_plan"
          }
        ],
        "input_mapping": {
          "account_risk_summary": {
            "limit": "$.input.limit",
            "owner_scope": "$.input.owner_scope",
            "quarter": "$.input.quarter",
            "ranking_basis": "$.input.ranking_basis"
          },
          "prepare_reassignment_plan": {
            "limit": "$.input.limit",
            "owner_scope": "$.input.owner_scope",
            "quarter": "$.input.quarter"
          }
        },
        "output_mapping": {
          "result": "$.steps.prepare_reassignment_plan.output.result"
        },
        "empty_result_policy": "return_success_no_results",
        "empty_result_output": {
          "empty": true,
          "result": null
        },
        "failure_policy": {
          "child_clarification": "propagate",
          "child_denial": "propagate",
          "child_approval_required": "propagate",
          "child_error": "fail_parent"
        },
        "audit_policy": {
          "record_child_invocations": true,
          "parent_task_lineage": true
        }
      },
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "application_integration",
      "service_id": "gtm-pipeline-service",
      "capability_id": "gtm.at_risk_reassignment_preparation",
      "title": "Gtm.At Risk Reassignment Preparation",
      "summary": "Compose gtm.account_risk_summary -\u003e gtm.prepare_reassignment_plan when the requested business action needs derived targets before governed preparation.",
      "subject_kind": "authorized GTM operator",
      "context_type": "quarter and optional owner scope",
      "output_intent": "operational preview",
      "intent_type": "business_action",
      "operation_type": "approval_gated",
      "side_effect_level": "approval_required",
      "implementation_fit": {
        "category": "native_anip",
        "rationale": "Represented as a declared contract-level composed business capability. Child handlers may still require service implementation."
      },
      "business_effects": {
        "produces": [
          "content.summary",
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "raw_data_export",
          "approval.execute"
        ]
      },
      "backend_operation": "gtm.at_risk_reassignment_preparation",
      "path_template": "/gtm/at-risk-reassignment-preparation",
      "output_shape": "gtm_at_risk_reassignment_preparation_result",
      "inputs": [
        {
          "input_name": "quarter",
          "input_type": "string",
          "required": true,
          "summary": "Quarter label like 2017-Q2",
          "default_value": "",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": true,
          "summary": "Risk ranking basis",
          "default_value": "risk_score",
          "allowed_values": [
            "risk_score"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Regional office or company",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        }
      ]
    },
    {
      "id": "composition:inferred:gtm_prioritize_accounts:gtm_route_leads",
      "kind": "composed",
      "composition": {
        "authority_boundary": "same_service",
        "steps": [
          {
            "id": "prioritize_accounts",
            "capability": "gtm.prioritize_accounts",
            "empty_result_source": true
          },
          {
            "id": "route_leads",
            "capability": "gtm.route_leads"
          }
        ],
        "input_mapping": {
          "prioritize_accounts": {
            "cohort_ref": "$.input.cohort_ref",
            "limit": "$.input.limit",
            "owner_scope": "$.input.owner_scope",
            "ranking_basis": "$.input.ranking_basis"
          },
          "route_leads": {
            "cohort_ref": "$.input.cohort_ref",
            "owner_scope": "$.input.owner_scope"
          }
        },
        "output_mapping": {
          "result": "$.steps.route_leads.output.result"
        },
        "empty_result_policy": "return_success_no_results",
        "empty_result_output": {
          "empty": true,
          "result": null
        },
        "failure_policy": {
          "child_clarification": "propagate",
          "child_denial": "propagate",
          "child_approval_required": "propagate",
          "child_error": "fail_parent"
        },
        "audit_policy": {
          "record_child_invocations": true,
          "parent_task_lineage": true
        }
      },
      "grant_policy": {
        "allowed_grant_types": [
          "one_time",
          "session_bound"
        ],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      },
      "source_kind": "application_integration",
      "service_id": "gtm-prioritization-service",
      "capability_id": "gtm.prioritized_routing_preparation",
      "title": "Gtm.Prioritized Routing Preparation",
      "summary": "Compose gtm.prioritize_accounts -\u003e gtm.route_leads when the requested business action needs derived targets before governed preparation.",
      "subject_kind": "rev ops manager or sales leader",
      "context_type": "cohort and optional ownership scope",
      "output_intent": "routing preview",
      "intent_type": "business_action",
      "operation_type": "approval_gated",
      "side_effect_level": "approval_required",
      "implementation_fit": {
        "category": "native_anip",
        "rationale": "Represented as a declared contract-level composed business capability. Child handlers may still require service implementation."
      },
      "business_effects": {
        "produces": [
          "content.recommendation",
          "approval.request",
          "system.preview_mutation"
        ],
        "does_not_produce": [
          "approval.execute"
        ]
      },
      "backend_operation": "gtm.prioritized_routing_preparation",
      "path_template": "/gtm/prioritized-routing-preparation",
      "output_shape": "gtm_prioritized_routing_preparation_result",
      "inputs": [
        {
          "input_name": "cohort_ref",
          "input_type": "string",
          "required": true,
          "summary": "Account cohort; map phrases like expansion candidates to expansion_candidates_q2 and at risk q2 to at_risk_q2",
          "default_value": "",
          "allowed_values": [
            "expansion_candidates_q2",
            "at_risk_q2"
          ],
          "semantic_type": "cohort_reference",
          "catalog_ref": "gtm.cohort_catalog",
          "resolution": {
            "mode": "closed_values",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "ranking_basis",
          "input_type": "string",
          "required": false,
          "summary": "Priority ranking basis",
          "default_value": "deal_likelihood",
          "allowed_values": [
            "deal_likelihood"
          ],
          "resolution": {
            "mode": "closed_values",
            "on_missing": "use_default",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "input_name": "limit",
          "input_type": "integer",
          "required": false,
          "summary": "Maximum accounts to return",
          "default_value": "",
          "resolution": {
            "mode": "explicit_only",
            "on_missing": "omit"
          }
        },
        {
          "input_name": "owner_scope",
          "input_type": "string",
          "required": false,
          "summary": "Actor-safe ownership scope",
          "default_value": "",
          "semantic_type": "scope_reference",
          "resolution": {
            "mode": "actor_policy_or_explicit",
            "on_missing": "use_actor_scope",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        }
      ]
    }
  ],
  "permission_intent_bindings": [
    {
      "id": "permission_rule_0",
      "actor_id": "sales_analyst",
      "business_area": "outreach_drafting",
      "business_area_label": "Outreach Drafting",
      "access_posture": "allowed",
      "governed_outcome_type": "direct_result",
      "governed_outcome": "Return bounded read results for in-scope pipeline, enrichment, prioritization, or outreach-draft requests.",
      "target_service_ids": [
        "gtm-outreach-service"
      ],
      "target_capability_ids": [
        "gtm.draft_outreach_message",
        "gtm.suggest_followup_content",
        "gtm.objection_response_variants",
        "gtm.bottleneck_account_outreach_draft",
        "gtm.prioritized_outreach_draft"
      ],
      "formalization_strategy": "sales_analyst allowed access to Outreach Drafting should return direct_result. Return bounded read results for in-scope pipeline, enrichment, prioritization, or outreach-draft requests. Use only after actor and business-area vocabularies are confirmed. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"sales_analyst\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"outreach_drafting\"."
    },
    {
      "id": "permission_rule_1",
      "actor_id": "sales_leader",
      "business_area": "pipeline_insight",
      "business_area_label": "Pipeline Insight",
      "access_posture": "bounded",
      "governed_outcome_type": "masked_or_restricted_result",
      "governed_outcome": "Return a narrowed or masked result when the actor can see the shape of the data but not the full scope or values.",
      "target_service_ids": [
        "gtm-pipeline-service"
      ],
      "target_capability_ids": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan",
        "gtm.at_risk_followup_preparation",
        "gtm.at_risk_reassignment_preparation"
      ],
      "formalization_strategy": "sales_leader bounded access to Pipeline Insight should return masked_or_restricted_result. Return a narrowed or masked result when the actor can see the shape of the data but not the full scope or values. Applies to partial visibility cases described in the forecast, bottleneck, team performance, and product pipeline specs. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"sales_leader\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"pipeline_insight\"."
    },
    {
      "id": "permission_rule_2",
      "actor_id": "account_manager_east",
      "business_area": "governance_and_approvals",
      "business_area_label": "Governance and Approvals",
      "access_posture": "restricted",
      "governed_outcome_type": "masked_or_restricted_result",
      "governed_outcome": "Restrict the requested region, ownership boundary, or slice when the actor is outside the allowed scope.",
      "target_service_ids": [
        "gtm-pipeline-service"
      ],
      "target_capability_ids": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan",
        "gtm.at_risk_followup_preparation",
        "gtm.at_risk_reassignment_preparation"
      ],
      "formalization_strategy": "account_manager_east restricted access to Governance and Approvals should return masked_or_restricted_result. Restrict the requested region, ownership boundary, or slice when the actor is outside the allowed scope. Use for actor-aware regional or ownership boundaries. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"account_manager_east\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"governance_and_approvals\"."
    },
    {
      "id": "permission_rule_3",
      "actor_id": "sales_analyst",
      "business_area": "account_enrichment",
      "business_area_label": "Account Enrichment",
      "access_posture": "denied",
      "governed_outcome_type": "deny_request",
      "governed_outcome": "Deny raw export, direct-send, unsupported analysis, or other out-of-scope requests instead of improvising unsafe behavior.",
      "target_service_ids": [
        "gtm-enrichment-service"
      ],
      "target_capability_ids": [
        "gtm.account_enrichment_summary",
        "gtm.lookalike_accounts"
      ],
      "formalization_strategy": "sales_analyst denied access to Account Enrichment should return deny_request. Deny raw export, direct-send, unsupported analysis, or other out-of-scope requests instead of improvising unsafe behavior. Covers raw CRM export, raw model-feature dumps, raw transcripts, and direct-send outreach. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"sales_analyst\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"account_enrichment\"."
    },
    {
      "id": "permission_rule_4",
      "actor_id": "rev_ops_manager",
      "business_area": "prioritization_and_routing",
      "business_area_label": "Prioritization and Routing",
      "access_posture": "approval_required",
      "governed_outcome_type": "approval_stop",
      "governed_outcome": "Prepare the operational preview, then stop before routing, reassignment, follow-up execution, or any downstream mutation.",
      "target_service_ids": [
        "gtm-pipeline-service"
      ],
      "target_capability_ids": [
        "gtm.at_risk_followup_preparation"
      ],
      "formalization_strategy": "rev_ops_manager approval_required access to Prioritization and Routing should return approval_stop. Prepare the operational preview, then stop before routing, reassignment, follow-up execution, or any downstream mutation. Applies to lead routing, reassignment previews, and follow-up task preparation. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"rev_ops_manager\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"prioritization_and_routing\"."
    },
    {
      "id": "permission_rule_5",
      "actor_id": "account_manager_east",
      "business_area": "prioritization_and_routing",
      "business_area_label": "Prioritization and Routing",
      "access_posture": "allowed",
      "governed_outcome_type": "clarification_required",
      "governed_outcome": "Ask for missing quarter, account reference, cohort, ranking basis, target, or other critical input instead of guessing.",
      "target_service_ids": [
        "gtm-prioritization-service"
      ],
      "target_capability_ids": [
        "gtm.prioritized_routing_preparation"
      ],
      "formalization_strategy": "account_manager_east allowed access to Prioritization and Routing should return clarification_required. Ask for missing quarter, account reference, cohort, ranking basis, target, or other critical input instead of guessing. Use when required parameters are missing from the request. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"account_manager_east\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"prioritization_and_routing\"."
    }
  ],
  "runtime_policy_bindings": [
    {
      "id": "policy_permission_rule_0",
      "source_permission_id": "permission_rule_0",
      "actor_id": "sales_analyst",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "sales_analyst"
      },
      "business_area": "outreach_drafting",
      "business_area_label": "Outreach Drafting",
      "service_ids": [
        "gtm-outreach-service"
      ],
      "capability_ids": [
        "gtm.draft_outreach_message",
        "gtm.suggest_followup_content",
        "gtm.objection_response_variants",
        "gtm.bottleneck_account_outreach_draft",
        "gtm.prioritized_outreach_draft"
      ],
      "decision": "allow",
      "business_rule": "Return bounded read results for in-scope pipeline, enrichment, prioritization, or outreach-draft requests.",
      "enforcement_notes": "sales_analyst allowed access to Outreach Drafting should return direct_result. Return bounded read results for in-scope pipeline, enrichment, prioritization, or outreach-draft requests. Use only after actor and business-area vocabularies are confirmed. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"sales_analyst\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"outreach_drafting\"."
    },
    {
      "id": "policy_permission_rule_1",
      "source_permission_id": "permission_rule_1",
      "actor_id": "sales_leader",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "sales_leader"
      },
      "business_area": "pipeline_insight",
      "business_area_label": "Pipeline Insight",
      "service_ids": [
        "gtm-pipeline-service"
      ],
      "capability_ids": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan",
        "gtm.at_risk_followup_preparation",
        "gtm.at_risk_reassignment_preparation"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Return a narrowed or masked result when the actor can see the shape of the data but not the full scope or values.",
      "enforcement_notes": "sales_leader bounded access to Pipeline Insight should return masked_or_restricted_result. Return a narrowed or masked result when the actor can see the shape of the data but not the full scope or values. Applies to partial visibility cases described in the forecast, bottleneck, team performance, and product pipeline specs. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"sales_leader\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"pipeline_insight\"."
    },
    {
      "id": "policy_permission_rule_2",
      "source_permission_id": "permission_rule_2",
      "actor_id": "account_manager_east",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "account_manager_east"
      },
      "business_area": "governance_and_approvals",
      "business_area_label": "Governance and Approvals",
      "service_ids": [
        "gtm-pipeline-service"
      ],
      "capability_ids": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan",
        "gtm.at_risk_followup_preparation",
        "gtm.at_risk_reassignment_preparation"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Restrict the requested region, ownership boundary, or slice when the actor is outside the allowed scope.",
      "enforcement_notes": "account_manager_east restricted access to Governance and Approvals should return masked_or_restricted_result. Restrict the requested region, ownership boundary, or slice when the actor is outside the allowed scope. Use for actor-aware regional or ownership boundaries. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"account_manager_east\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"governance_and_approvals\"."
    },
    {
      "id": "policy_permission_rule_3",
      "source_permission_id": "permission_rule_3",
      "actor_id": "sales_analyst",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "sales_analyst"
      },
      "business_area": "account_enrichment",
      "business_area_label": "Account Enrichment",
      "service_ids": [
        "gtm-enrichment-service"
      ],
      "capability_ids": [
        "gtm.account_enrichment_summary",
        "gtm.lookalike_accounts"
      ],
      "decision": "deny",
      "business_rule": "Deny raw export, direct-send, unsupported analysis, or other out-of-scope requests instead of improvising unsafe behavior.",
      "enforcement_notes": "sales_analyst denied access to Account Enrichment should return deny_request. Deny raw export, direct-send, unsupported analysis, or other out-of-scope requests instead of improvising unsafe behavior. Covers raw CRM export, raw model-feature dumps, raw transcripts, and direct-send outreach. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"sales_analyst\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"account_enrichment\"."
    },
    {
      "id": "policy_permission_rule_4",
      "source_permission_id": "permission_rule_4",
      "actor_id": "rev_ops_manager",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "rev_ops_manager"
      },
      "business_area": "prioritization_and_routing",
      "business_area_label": "Prioritization and Routing",
      "service_ids": [
        "gtm-pipeline-service"
      ],
      "capability_ids": [
        "gtm.at_risk_followup_preparation"
      ],
      "decision": "approval_required",
      "business_rule": "Prepare the operational preview, then stop before routing, reassignment, follow-up execution, or any downstream mutation.",
      "enforcement_notes": "rev_ops_manager approval_required access to Prioritization and Routing should return approval_stop. Prepare the operational preview, then stop before routing, reassignment, follow-up execution, or any downstream mutation. Applies to lead routing, reassignment previews, and follow-up task preparation. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"rev_ops_manager\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"prioritization_and_routing\"."
    },
    {
      "id": "policy_permission_rule_5",
      "source_permission_id": "permission_rule_5",
      "actor_id": "account_manager_east",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "account_manager_east"
      },
      "business_area": "prioritization_and_routing",
      "business_area_label": "Prioritization and Routing",
      "service_ids": [
        "gtm-prioritization-service"
      ],
      "capability_ids": [
        "gtm.prioritized_routing_preparation"
      ],
      "decision": "clarify",
      "business_rule": "Ask for missing quarter, account reference, cohort, ranking basis, target, or other critical input instead of guessing.",
      "enforcement_notes": "account_manager_east allowed access to Prioritization and Routing should return clarification_required. Ask for missing quarter, account reference, cohort, ranking basis, target, or other critical input instead of guessing. Use when required parameters are missing from the request. Studio mapped assistant actor reference \"\u003crequires_clarification\u003e\" to existing actor \"account_manager_east\". Studio mapped assistant business-area reference \"\u003crequires_clarification\u003e\" to existing business area \"prioritization_and_routing\"."
    }
  ],
  "integration_fronting": {
    "project_type": "standard"
  }
}
) as const;
