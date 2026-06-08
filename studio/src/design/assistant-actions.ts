import {
  proposeActorModelWithAssistant,
  proposeBackendBindingsWithAssistant,
  proposeBusinessAreasWithAssistant,
  proposeBusinessSummaryWithAssistant,
  proposeCapabilityFormalizationWithAssistant,
  identifyMissingBusinessInfoWithAssistant,
  proposeInputContractsWithAssistant,
  proposeNonGoalsWithAssistant,
  proposePermissionIntentWithAssistant,
  proposeRequirementsWithAssistant,
  proposeRuntimePolicyBindingsWithAssistant,
  proposeScenariosWithAssistant,
  proposeServiceDesignWithAssistant,
  proposeSuccessCriteriaWithAssistant,
  proposeVerificationExpectationsWithAssistant,
} from './project-api'
import type { AssistantProposalEnvelope, AssistantServiceTopologyPreference } from './project-types'
import {
  capabilityFormalizationEvidenceArtifactItems,
  inputContractEvidenceArtifactItems,
  parseCapabilityFormalizationEvidenceFromSourceText,
  parseInputContractEvidenceFromSourceText,
} from './input-contract-evidence'

export type PmAssistantActionKey =
  | 'requirements'
  | 'scenarios'
  | 'service_design'
  | 'business_summary'
  | 'actor_model'
  | 'business_areas'
  | 'permission_intent'
  | 'non_goals'
  | 'success_criteria'
  | 'missing_info'

export type DevAssistantActionKey =
  | 'service_design'
  | 'capability_formalization'
  | 'runtime_policy_bindings'
  | 'input_contracts'
  | 'verification_expectations'
  | 'backend_bindings'

export interface AssistantActionButton<ActionKey extends string> {
  key: ActionKey
  label: string
}

export const pmAssistantButtons: AssistantActionButton<PmAssistantActionKey>[] = [
  { key: 'requirements', label: 'Propose Requirements' },
  { key: 'scenarios', label: 'Propose Scenarios' },
  { key: 'business_summary', label: 'Propose Summary' },
  { key: 'actor_model', label: 'Propose Actors' },
  { key: 'business_areas', label: 'Propose Areas' },
  { key: 'permission_intent', label: 'Propose Permissions' },
  { key: 'non_goals', label: 'Propose Non-Goals' },
  { key: 'success_criteria', label: 'Propose Success' },
  { key: 'missing_info', label: 'Identify Missing Info' },
]

export const devAssistantButtons: AssistantActionButton<DevAssistantActionKey>[] = [
  { key: 'service_design', label: 'Propose Service Design' },
  { key: 'capability_formalization', label: 'Propose Capability Formalization' },
  { key: 'runtime_policy_bindings', label: 'Propose Runtime Policy Bindings' },
  { key: 'input_contracts', label: 'Propose Input Contracts' },
  { key: 'verification_expectations', label: 'Propose Evidence & Verification Plan' },
  { key: 'backend_bindings', label: 'Propose Runtime Backends' },
]

const pmSectionActionMap: Record<string, PmAssistantActionKey> = {
  product_summary: 'business_summary',
  actor_model: 'actor_model',
  business_areas: 'business_areas',
  permission_intent: 'permission_intent',
  non_goals: 'non_goals',
  success_criteria: 'success_criteria',
}

const devSectionActionMap: Record<string, DevAssistantActionKey> = {
  service_identity_topology: 'service_design',
  capability_contracts: 'capability_formalization',
  authority_and_approval: 'runtime_policy_bindings',
  backend_bindings: 'backend_bindings',
  audit_and_lineage: 'verification_expectations',
}

export const developerDefinitionNavigationSectionKeys = new Set([
  'data_contracts',
  'scenario_context',
  'execution_semantics',
  'generation_and_extensions',
])

export function pmActionForSection(sectionKey: string): PmAssistantActionKey {
  return pmSectionActionMap[sectionKey] ?? 'missing_info'
}

export function devActionForSection(sectionKey: string): DevAssistantActionKey {
  return devSectionActionMap[sectionKey] ?? 'service_design'
}

export function isDeveloperSectionNavigationOnly(sectionKey: string): boolean {
  return developerDefinitionNavigationSectionKeys.has(sectionKey)
}

export async function runPmAssistantAction(
  action: PmAssistantActionKey,
  args: {
    projectId: string
    sourceText: string
    sourceRequirementsId?: string | null
    useDeterministic?: boolean
    serviceTopologyPreference?: AssistantServiceTopologyPreference | null
    signal?: AbortSignal
  },
): Promise<AssistantProposalEnvelope> {
  const { projectId, sourceText, sourceRequirementsId, useDeterministic = false, serviceTopologyPreference = null, signal } = args
  switch (action) {
    case 'requirements':
      return proposeRequirementsWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'scenarios':
      return proposeScenariosWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'service_design':
      return proposeServiceDesignWithAssistant(projectId, sourceText, sourceRequirementsId, null, useDeterministic, serviceTopologyPreference, { signal })
    case 'business_summary':
      return proposeBusinessSummaryWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'actor_model':
      return proposeActorModelWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'business_areas':
      return proposeBusinessAreasWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'permission_intent':
      return proposePermissionIntentWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'non_goals':
      return proposeNonGoalsWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'success_criteria':
      return proposeSuccessCriteriaWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
    case 'missing_info':
      return identifyMissingBusinessInfoWithAssistant(projectId, sourceText, sourceRequirementsId, useDeterministic, { signal })
  }
}

export async function runDevAssistantAction(
  action: DevAssistantActionKey,
  args: {
    projectId: string
    sourceText: string
    sourceRequirementsId?: string | null
    sourceShapeId?: string | null
    useDeterministic?: boolean
    serviceTopologyPreference?: AssistantServiceTopologyPreference | null
    signal?: AbortSignal
  },
): Promise<AssistantProposalEnvelope> {
  const { projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic = false, serviceTopologyPreference = null, signal } = args
  switch (action) {
    case 'service_design':
      return proposeServiceDesignWithAssistant(projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic, serviceTopologyPreference, { signal })
    case 'capability_formalization':
      try {
        const evidence = parseCapabilityFormalizationEvidenceFromSourceText(sourceText)
        const items = capabilityFormalizationEvidenceArtifactItems(evidence)
        return {
          title: 'Reviewed Capability Formalizations',
          summary: `Extracted ${evidence.capabilities.length} reviewed capability formalization${evidence.capabilities.length === 1 ? '' : 's'} from developer source evidence. Review before saving contract truth.`,
          mode: 'dev',
          capability: 'propose_capability_formalization',
          questions_for_user: [],
          watchouts: evidence.warnings,
          next_steps: [
            'Review the extracted capability formalizations in Capability Formalization.',
            'Save only after the developer-owned interface evidence matches the intended runtime surface.',
          ],
          proposal: {
            proposal_kind: 'candidate_blocks',
            artifact_type: 'capability_formalization',
            items: items.map((item) => ({
              client_id: String(item.client_id),
              title: String(item.title),
              body: String(item.body ?? 'Reviewed developer source evidence provided concrete capability formalizations.'),
              confidence: 'high',
              rationale: 'Extracted directly from developer-owned structured capability-formalization evidence; no model inference was required.',
              structured_data: item.structured_data as Record<string, any>,
            })),
          },
        }
      } catch {
        // Fall back to the assistant when the selected source does not contain structured capability evidence.
      }
      return proposeCapabilityFormalizationWithAssistant(projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic, { signal })
    case 'runtime_policy_bindings':
      return proposeRuntimePolicyBindingsWithAssistant(projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic, { signal })
    case 'input_contracts':
      try {
        const evidence = parseInputContractEvidenceFromSourceText(sourceText)
        const items = inputContractEvidenceArtifactItems(evidence)
        return {
          title: 'Reviewed Input Contracts',
          summary: `Extracted ${evidence.capabilities.length} reviewed capability input contract${evidence.capabilities.length === 1 ? '' : 's'} from developer source evidence. Review before saving contract truth.`,
          mode: 'dev',
          capability: 'propose_input_contracts',
          questions_for_user: [],
          watchouts: evidence.warnings,
          next_steps: [
            'Review the extracted input contracts in Capability Formalization.',
            'Save only after the developer-owned interface evidence matches the intended runtime surface.',
          ],
          proposal: {
            proposal_kind: 'candidate_blocks',
            artifact_type: 'assistant_input_contract_candidates',
            items: items.map((item) => ({
              client_id: String(item.client_id),
              title: String(item.title),
              body: 'Reviewed developer source evidence provided concrete input names, types, required flags, defaults, allowed values, and resolution metadata.',
              confidence: 'high',
              rationale: 'Extracted directly from developer-owned structured input-contract evidence; no model inference was required.',
              structured_data: item.structured_data as Record<string, any>,
            })),
          },
        }
      } catch {
        // Fall back to the assistant when the selected source does not contain structured input-contract evidence.
      }
      return proposeInputContractsWithAssistant(projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic, { signal })
    case 'verification_expectations':
      return proposeVerificationExpectationsWithAssistant(projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic, { signal })
    case 'backend_bindings':
      return proposeBackendBindingsWithAssistant(projectId, sourceText, sourceRequirementsId, sourceShapeId, useDeterministic, { signal })
  }
}
