// Generated runtime target metadata.

export type GeneratedBackendBinding = {
  backend_kind: string;
  connection_ref: string;
  raw_operation_refs: string[];
  backend_input_mode?: "implicit" | "hybrid" | "explicit";
  derived_required_backend_inputs?: string[];
  derived_optional_backend_inputs?: string[];
  explicit_required_backend_inputs?: string[];
  explicit_optional_backend_inputs?: string[];
  matched_discovery_record_ids?: string[];
  status?: string;
  status_detail?: string;
};

export type GeneratedCapabilityInputMetadata = {
  input_name: string;
  input_type: string;
  required: boolean;
  summary: string;
  default_value: string;
  allowed_values: string[];
  [key: string]: unknown;
};

export type GeneratedCapabilityRuntimeMetadata = {
  service_id: string;
  service_name: string;
  capability_id: string;
  title: string;
  summary: string;
  intent_type: string;
  operation_type: string;
  execution_posture: string;
  side_effect_level: string;
  backend_operation: string;
  path_template: string;
  output_shape: string;
  subject_kind: string;
  context_type: string;
  output_intent: string;
  minimum_scope: string[];
  required_inputs: GeneratedCapabilityInputMetadata[];
  optional_inputs: GeneratedCapabilityInputMetadata[];
  sample_parameters: Record<string, unknown>;
  backend_input_mode: "implicit" | "hybrid" | "explicit";
  derived_required_backend_inputs: string[];
  derived_optional_backend_inputs: string[];
  explicit_required_backend_inputs: string[];
  explicit_optional_backend_inputs: string[];
  backend_bindings: GeneratedBackendBinding[];
  governance: {
    approval_rule_refs: string[];
    denial_rule_refs: string[];
    clarification_rule_refs: string[];
    audit_required: boolean;
  };
  outbound_controls: unknown;
};

export type EffectiveBackendInputContract = {
  mode: "implicit" | "hybrid" | "explicit";
  required: string[];
  optional: string[];
};

export type BackendInvocationPlan = {
  selected_binding: GeneratedBackendBinding | null;
  semantic_input: Record<string, unknown>;
  backend_input_contract: EffectiveBackendInputContract;
  unresolved_required_backend_inputs: string[];
};

export const runtimeTarget = {
  "system_name": "GTM Pipeline Q2 Review",
  "domain_name": "revenue_operations",
  "delivery_model": "standalone_service",
  "architecture_shape": "single_service",
  "protocols": [
    "anip_http"
  ],
  "services": [
    {
      "service_id": "gtm-pipeline-service",
      "service_name": "GTM Pipeline Service",
      "source_role": "answers bounded pipeline review questions and prepares follow-up and reassignment previews",
      "source_capabilities": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.prepare_reassignment_plan",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks"
      ],
      "formalized_capability_ids": [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.prepare_reassignment_plan",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks"
      ],
      "owned_concept_ids": [
        "pipeline-review",
        "account-risk",
        "followup-plan",
        "reassignment-plan"
      ]
    }
  ],
  "authority": {
    "approval_expectation": "approval_required_for_high_risk",
    "blocked_failure_posture": "human_review_for_unresolved_or_approval_gated_work"
  },
  "audit": {
    "durable_records_required": true,
    "searchable_history_required": true
  }
} as const;

export const generatedCapabilityMetadata: GeneratedCapabilityRuntimeMetadata[] = [
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.pipeline_summary",
    "title": "Gtm.Pipeline Summary",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.pipeline_summary",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.pipeline_summary"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.pipeline_forecast_summary",
    "title": "Gtm.Pipeline Forecast Summary",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.pipeline_forecast_summary",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.pipeline_forecast_summary"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.stage_bottleneck_summary",
    "title": "Gtm.Stage Bottleneck Summary",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.stage_bottleneck_summary",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.stage_bottleneck_summary"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.sales_team_performance_summary",
    "title": "Gtm.Sales Team Performance Summary",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.sales_team_performance_summary",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.sales_team_performance_summary"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.product_pipeline_summary",
    "title": "Gtm.Product Pipeline Summary",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.product_pipeline_summary",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.product_pipeline_summary"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.prepare_reassignment_plan",
    "title": "Gtm.Prepare Reassignment Plan",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.prepare_reassignment_plan",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.prepare_reassignment_plan"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.stalled_opportunity_review",
    "title": "Gtm.Stalled Opportunity Review",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.stalled_opportunity_review",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.stalled_opportunity_review"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.account_risk_summary",
    "title": "Gtm.Account Risk Summary",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.account_risk_summary",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.account_risk_summary"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  },
  {
    "service_id": "gtm-pipeline-service",
    "service_name": "GTM Pipeline Service",
    "capability_id": "gtm.prepare_followup_tasks",
    "title": "Gtm.Prepare Followup Tasks",
    "summary": "Capability owned by GTM Pipeline Service.",
    "intent_type": "business_action",
    "operation_type": "read",
    "execution_posture": "business_action",
    "side_effect_level": "none",
    "backend_operation": "gtm.prepare_followup_tasks",
    "path_template": "",
    "output_shape": "governed_result",
    "subject_kind": "record",
    "context_type": "governed_request",
    "output_intent": "governed_result",
    "minimum_scope": [
      "gtm.prepare_followup_tasks"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "implicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": false
    },
    "outbound_controls": {}
  }
];
