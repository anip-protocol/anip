import { projectPathFromParts } from './project-routes'

export type AssistantStepActionTone = 'primary' | 'secondary'

export interface AssistantStepAction {
  id: string
  label: string
  tone: AssistantStepActionTone
  path?: string
  event?: 'run_simulator' | 'save_readiness_handoff' | 'download_readiness_handoff'
}

function includesAny(value: string, tokens: string[]): boolean {
  return tokens.some((token) => value.includes(token))
}

function route(projectId: string, workspaceId: string | null | undefined, suffix: string): string {
  return projectPathFromParts(projectId, workspaceId, suffix)
}

export function assistantStepActionsForText(
  text: string,
  projectId: string | null | undefined,
  workspaceId?: string | null,
): AssistantStepAction[] {
  if (!projectId) return []
  const normalized = text.toLowerCase()
  const actions: AssistantStepAction[] = []

  function add(action: AssistantStepAction) {
    if (actions.some((item) => item.id === action.id)) return
    actions.push(action)
  }

  if (includesAny(normalized, ['rerun the simulator', 'run the simulator', 'run ai simulator', 'simulator afterward'])) {
    add({
      id: 'run-simulator',
      label: 'Run simulator',
      tone: 'primary',
      event: 'run_simulator',
    })
  }

  if (includesAny(normalized, ['attach this passing simulator report', 'attach this simulator report', 'readiness or publication review', 'regression evidence', 'handoff artifact'])) {
    add({
      id: 'save-readiness-handoff',
      label: 'Save handoff artifact',
      tone: 'primary',
      event: 'save_readiness_handoff',
    })
  }

  if (includesAny(normalized, ['download report', 'download json', 'export report'])) {
    add({
      id: 'download-readiness-handoff',
      label: 'Download report JSON',
      tone: 'secondary',
      event: 'download_readiness_handoff',
    })
  }

  if (includesAny(normalized, ['app glue', 'app-glue', 'agent readiness', 'consumability', 'readiness findings', 'readiness review'])) {
    add({
      id: 'open-app-glue',
      label: 'Open Agent & App Glue',
      tone: 'secondary',
      path: route(projectId, workspaceId, '/developer/app-glue'),
    })
  }

  if (includesAny(normalized, ['app profile', 'runtime customization', 'runtime overrides', 'customization files', 'agent app customization'])) {
    add({
      id: 'open-app-customization',
      label: 'Open Agent App Customization',
      tone: 'secondary',
      path: route(projectId, workspaceId, '/developer/app-customization'),
    })
  }

  if (includesAny(normalized, ['developer coverage', 'coverage mapping', 'inspect whether there are untested scenarios'])) {
    add({
      id: 'open-coverage',
      label: 'Open Coverage',
      tone: 'secondary',
      path: route(projectId, workspaceId, '/developer/coverage'),
    })
  }

  if (includesAny(normalized, ['developer definition', 'compiled contract', 'save developer definition', 'contract'])) {
    add({
      id: 'open-definition',
      label: 'Open Developer Definition',
      tone: 'secondary',
      path: route(projectId, workspaceId, '/developer/definition'),
    })
  }

  if (includesAny(normalized, ['generator', 'generation', 'generate', 'code generation'])) {
    add({
      id: 'open-generation',
      label: 'Open Generation',
      tone: 'primary',
      path: `${route(projectId, workspaceId, '/developer/definition')}#generation-launch`,
    })
  }

  if (includesAny(normalized, ['verifier', 'verification', 'verify'])) {
    add({
      id: 'open-verification',
      label: 'Open Verification',
      tone: 'primary',
      path: route(projectId, workspaceId, '/verification'),
    })
  }

  if (includesAny(normalized, ['publication', 'publish', 'registry'])) {
    add({
      id: 'open-publication',
      label: 'Open Publication',
      tone: 'primary',
      path: route(projectId, workspaceId, '/developer/definition'),
    })
  }

  return actions
}
