export interface PackMeta {
  id: string            // directory name, e.g. "travel-single"
  name: string          // from requirements.system.name or scenario.scenario.name
  domain: string        // from requirements.system.domain
  category: string      // from scenario.scenario.category
  narrative: string     // from scenario.scenario.narrative (truncated for cards)
  result: string | null // from evaluation.evaluation.result, or null when missing
  isMultiService: boolean // from requirements or directory name heuristic
}

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

export interface Scenario {
  scenario: {
    name: string
    category: string
    narrative: string
    context: Record<string, any>
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
  }
}

export interface DesignPack {
  meta: PackMeta
  requirements: Requirements
  proposal: Proposal | null
  scenario: Scenario
  evaluation: Evaluation | null
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
}

export type EditState = 'read' | 'draft' | 'exported'

export type RequirementsMode = 'guided' | 'advanced'

export type ScenarioMode = 'guided' | 'advanced'
