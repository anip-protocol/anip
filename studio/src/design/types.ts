export interface Requirements {
  system: { name: string; domain: string; deployment_intent: string }
  services?: Array<Record<string, any>>
  transports: Record<string, boolean>
  trust: { mode: string; checkpoints: boolean }
  auth?: Record<string, boolean>
  permissions?: Record<string, boolean>
  audit?: Record<string, boolean>
  lineage?: Record<string, boolean>
  risk_profile?: Record<string, any>
  business_constraints?: Record<string, boolean | string | number>
  scale?: Record<string, any>
  [key: string]: any
}

export interface Proposal {
  proposal: {
    recommended_shape: string
    rationale: string[]
    required_components: string[]
    optional_components?: string[]
    key_runtime_requirements?: string[]
    anti_pattern_warnings: string[]
    expected_glue_reduction: Record<string, string[]>
    [key: string]: any
  }
}

export type ScenarioAdditionalContextSemanticType =
  | 'descriptive_only'
  | 'actor_context'
  | 'business_scope'
  | 'time_scope'
  | 'participating_services'
  | 'orchestration_step'

export interface ScenarioAdditionalContextEntry {
  key: string
  value: any
  semantic_type?: ScenarioAdditionalContextSemanticType
  role?: 'descriptive' | 'design_driving'
  description?: string
}

export interface Scenario {
  scenario: {
    name: string
    category: string
    narrative: string
    context: Record<string, any>
    participating_services?: string[]
    orchestration_steps?: string[]
    additional_context?: ScenarioAdditionalContextEntry[]
    expected_behavior: string[]
    expected_anip_support: string[]
  }
}

export interface Evaluation {
  evaluation: {
    scenario_name: string
    result: 'HANDLED' | 'PARTIAL' | 'REQUIRES_GLUE'
    handled_by_anip: string[]
    glue_you_will_still_write: string[]
    glue_category: string[]
    why: string[]
    what_would_improve: string[]
    confidence?: string
    notes?: string[]
    runtime_observations?: RuntimeObservation
    runtime_observation_history?: RuntimeObservation[]
  }
}

export interface RuntimeObservation {
  observation_id: string
  source?: 'invoke' | 'audit'
  observed_at?: string | null
  invocation_id?: string | null
  task_id?: string | null
  parent_invocation_id?: string | null
  invoked_capability: string
  observed_outcome?: 'available' | 'restricted' | 'denied' | 'clarification_required' | 'approval_required' | null
  reason_code?: string | null
  unresolved_inputs?: string[]
  retry_without_progress?: boolean
  agent_behavior?: string | null
  backend_context?: string | null
}

export interface ObservedServiceCapability {
  id: string
  side_effect?: string | null
  minimum_scope: string[]
  financial: boolean
  contract?: string | null
  requires_binding: string[]
  control_requirements: string[]
  refresh_via: string[]
  verify_via: string[]
  followup_via: string[]
  cross_service_handoff: string[]
  cross_service_refresh: string[]
  cross_service_verify: string[]
  cross_service_followup: string[]
}

export interface ObservedServiceMetadata {
  source: 'inspect_discovery' | 'inspect_manifest' | 'inspect_discovery_manifest'
  observed_at: string
  generation_run_artifact_id?: string | null
  generation_dependency_source?: 'local' | 'registry' | null
  service_id?: string | null
  base_url?: string | null
  protocol?: string | null
  profile?: string | null
  compliance?: string | null
  trust_level?: string | null
  audit_retention?: string | null
  failure_detail_level?: string | null
  anchoring_enabled?: boolean | null
  signature_present?: boolean | null
  manifest_version?: string | null
  issuer_mode?: string | null
  jwks_uri_present?: boolean | null
  capabilities: ObservedServiceCapability[]
}

export interface IntendedDesignMetadata {
  shape_type?: string | null
  services: string[]
  capabilities: string[]
  declared_surfaces: string[]
}

export interface SurfaceEvidence {
  surface: string
  status: 'observed' | 'partially_observed' | 'not_observed' | 'needs_deeper_inspection'
  detail: string
}

export interface ConformanceCheck {
  id: string
  label: string
  status: 'conformant' | 'non_conformant' | 'insufficient_metadata'
  detail: string
  source: 'manifest' | 'discovery' | 'combined'
  related_surface?: string | null
}

export interface ServiceMetadataComparison {
  intended: IntendedDesignMetadata
  observed: ObservedServiceMetadata
  aligned_capabilities: string[]
  missing_capabilities: string[]
  extra_capabilities: string[]
  surface_evidence: SurfaceEvidence[]
  conformance_checks: ConformanceCheck[]
}

export interface DeclaredSurfaces {
  budget_enforcement: boolean
  binding_requirements: boolean
  authority_posture: boolean
  recovery_class: boolean
  refresh_via: boolean
  verify_via: boolean
  followup_via: boolean
  cross_service_handoff: boolean
  cross_service_continuity: boolean
  cross_service_reconstruction: boolean
}

export interface ValidationError {
  path: string
  message: string
  keyword?: string
  params?: Record<string, unknown>
}

export type EditState = 'read' | 'draft' | 'exported'

export type RequirementsMode = 'guided' | 'advanced'

export type ScenarioMode = 'guided' | 'advanced'
