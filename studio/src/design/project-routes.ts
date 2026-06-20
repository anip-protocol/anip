export interface ProjectRouteIdentity {
  id: string
  workspace_id?: string | null
}

function cleanSuffix(suffix = ''): string {
  const trimmed = String(suffix || '').trim()
  if (!trimmed) return ''
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`
}

function encodePathPart(value: string): string {
  return encodeURIComponent(value)
}

export function legacyProjectPath(projectId: string, suffix = ''): string {
  return `/design/projects/${encodePathPart(projectId)}${cleanSuffix(suffix)}`
}

export function workspaceProjectPathPrefix(workspaceId: string, projectId: string): string {
  return `/design/workspaces/${encodePathPart(workspaceId)}/projects/${encodePathPart(projectId)}`
}

export function projectPathFromParts(
  projectId: string,
  workspaceId?: string | null,
  suffix = '',
): string {
  if (workspaceId) {
    return `${workspaceProjectPathPrefix(workspaceId, projectId)}${cleanSuffix(suffix)}`
  }
  return legacyProjectPath(projectId, suffix)
}

export function projectPath(project: ProjectRouteIdentity, suffix = ''): string {
  return projectPathFromParts(project.id, project.workspace_id, suffix)
}

export function isLegacyProjectPath(path: string): boolean {
  return /^\/design\/projects\/[^/]+(?:\/.*)?$/.test(path)
}

export function canonicalProjectPathForSuffix(
  project: ProjectRouteIdentity,
  legacyPath: string,
): string {
  const prefix = `/design/projects/${encodePathPart(project.id)}`
  const suffix = legacyPath.startsWith(prefix) ? legacyPath.slice(prefix.length) : ''
  return projectPath(project, suffix)
}
