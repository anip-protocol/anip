import { computed, type Ref } from 'vue'
import {
  validateDeveloperDefinitionRequiredFields,
} from './developer-definition'
import {
  buildHighRiskConfirmationReport,
  highRiskConfirmationReportFromArtifacts,
  unresolvedHighRiskConfirmationItems,
} from './high-risk-confirmations'
import {
  projectStore,
} from './project-store'
import type {
  DeveloperDefinitionData,
  DeveloperServiceTopologyBinding,
  ProjectDetail,
} from './project-types'

export function useDeveloperIssueTargets(params: {
  definition: Ref<DeveloperDefinitionData | null | undefined>
  project?: Ref<ProjectDetail | null | undefined>
}) {
  const validationIssues = computed(() => params.definition.value
    ? validateDeveloperDefinitionRequiredFields(params.definition.value)
    : [])

  const validationIssueMessagesByPath = computed(() => {
    const result = new Map<string, string[]>()
    validationIssues.value.forEach((issue) => {
      const messages = result.get(issue.path) ?? []
      messages.push(issue.message)
      result.set(issue.path, messages)
    })
    return result
  })

  const highRiskReport = computed(() => {
    const project = params.project?.value ?? projectStore.activeProject
    if (!project) return null
    return buildHighRiskConfirmationReport({
      project,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      documents: projectStore.artifacts.documents,
      requirements: projectStore.artifacts.requirements,
      scenarios: projectStore.artifacts.scenarios,
      shapes: projectStore.artifacts.shapes,
      existing: highRiskConfirmationReportFromArtifacts(projectStore.artifacts.pmArtifacts),
    })
  })

  const unresolvedHighRiskItems = computed(() =>
    unresolvedHighRiskConfirmationItems(highRiskReport.value),
  )

  const serviceCapabilityCoverageItem = computed(() =>
    unresolvedHighRiskItems.value.find((item) => item.id === 'service-ownership:services-without-capabilities') ?? null,
  )

  const servicesWithoutCanonicalCapabilities = computed(() =>
    new Set(serviceCapabilityCoverageItem.value?.related_ids ?? []),
  )

  function messagesForPath(path: string): string[] {
    return validationIssueMessagesByPath.value.get(path) ?? []
  }

  function hasIssueForPath(path: string): boolean {
    return messagesForPath(path).length > 0
  }

  function messagesForPrefix(prefix: string): string[] {
    return validationIssues.value
      .filter((issue) => issue.path === prefix || issue.path.startsWith(`${prefix}.`))
      .map((issue) => issue.message)
  }

  function hasIssueForPrefix(prefix: string): boolean {
    return messagesForPrefix(prefix).length > 0
  }

  function serviceIssuePaths(service: DeveloperServiceTopologyBinding): string[] {
    const basePath = `service_topology_bindings.${service.id}`
    return [
      `${basePath}.formalized_capability_ids`,
    ]
  }

  function serviceValidationMessages(service: DeveloperServiceTopologyBinding): string[] {
    return serviceIssuePaths(service).flatMap((path) => messagesForPath(path))
  }

  function serviceNeedsCapabilityConfirmation(service: DeveloperServiceTopologyBinding): boolean {
    return servicesWithoutCanonicalCapabilities.value.has(service.service_id)
  }

  function serviceHasIssue(service: DeveloperServiceTopologyBinding): boolean {
    return serviceValidationMessages(service).length > 0 || serviceNeedsCapabilityConfirmation(service)
  }

  return {
    validationIssues,
    highRiskReport,
    unresolvedHighRiskItems,
    messagesForPath,
    hasIssueForPath,
    messagesForPrefix,
    hasIssueForPrefix,
    serviceValidationMessages,
    serviceNeedsCapabilityConfirmation,
    serviceHasIssue,
  }
}
