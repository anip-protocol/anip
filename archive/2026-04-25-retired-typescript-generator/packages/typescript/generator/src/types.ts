export type DependencySource = "registry" | "local";
export type HttpRuntime = "hono";

export interface AnipServiceDefinition {
  artifact_type?: string;
  contract_schema_version?: string;
  compiled_contract_identity?: {
    signature?: string | null;
    signature_algorithm?: string;
  };
  identity?: {
    system_name?: string;
    domain_name?: string;
    delivery_model?: string;
    architecture_shape?: string;
  };
  authority?: {
    approval_expectation?: string;
    blocked_failure_posture?: string;
  };
  audit?: {
    durable_records_required?: boolean;
    searchable_history_required?: boolean;
  };
  generation?: {
    protocols?: string[];
    layout_strategy?: string;
    selected_service_ids?: string[];
  };
  service_topology_bindings?: ServiceTopologyBinding[];
  capability_formalizations?: CapabilityFormalization[];
  integration_fronting?: {
    project_type?: string | null;
    capability_mappings?: IntegrationCapabilityMapping[];
  };
}

export interface ServiceTopologyBinding {
  id?: string;
  service_id: string;
  service_name?: string;
  source_role?: string;
  source_capabilities?: string[];
  formalized_capability_ids?: string[];
  owned_concept_ids?: string[];
}

export interface CapabilityFormalization {
  id?: string;
  source_kind?: string;
  service_id: string;
  capability_id: string;
  title: string;
  summary: string;
  entity_targeted?: boolean;
  subject_kind?: string;
  context_type?: string;
  output_intent?: string;
  intent_type: string;
  operation_type: string;
  side_effect_level: string;
  backend_operation: string;
  path_template: string;
  output_shape: string;
  inputs: CapabilityInputFormalization[];
}

export interface CapabilityInputFormalization {
  input_name: string;
  input_type: string;
  required: boolean;
  summary: string;
  default_value: string;
  allowed_values: string[];
  entity_reference?: boolean;
  semantic_aliases?: string[];
  [key: string]: unknown;
}

export interface IntegrationCapabilityMapping {
  id?: string;
  capability_id: string;
  title?: string;
  intent?: string;
  service_id: string;
  service_name?: string;
  backend_kind: string;
  connection_ref: string;
  raw_operation_refs: string[];
  backend_bindings?: IntegrationBackendBinding[];
  execution_posture: string;
  side_effect_level: string;
  subject_kind?: string;
  context_type?: string;
  output_intent?: string;
  required_inputs: string[];
  optional_inputs: string[];
  backend_input_mode?: "implicit" | "hybrid" | "explicit";
  derived_required_backend_inputs?: string[];
  derived_optional_backend_inputs?: string[];
  explicit_required_backend_inputs?: string[];
  explicit_optional_backend_inputs?: string[];
  approval_rule_refs?: string[];
  denial_rule_refs?: string[];
  clarification_rule_refs?: string[];
  audit_required?: boolean;
  outbound_controls?: unknown;
}

export interface IntegrationBackendBinding {
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
}

export interface GenerateTypeScriptProjectOptions {
  outputDir: string;
  definitionPath?: string;
  dependencySource?: DependencySource;
  httpRuntime?: HttpRuntime;
  packageName?: string;
  port?: number;
  force?: boolean;
}

export interface BuildTypeScriptProjectOptions {
  dependencySource: DependencySource;
  httpRuntime: HttpRuntime;
  packageName?: string;
  port: number;
}

export interface GeneratedTypeScriptProject {
  packageName: string;
  systemName: string;
  files: Array<{ path: string; content: string }>;
}
