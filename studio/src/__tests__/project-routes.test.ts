import { describe, expect, it } from 'vitest'
import {
  canonicalProjectPathForSuffix,
  isLegacyProjectPath,
  legacyProjectPath,
  projectPath,
  projectPathFromParts,
  workspaceProjectPathPrefix,
} from '../design/project-routes'

describe('project route helpers', () => {
  it('generates workspace-scoped project URLs when workspace identity is available', () => {
    expect(projectPath({ id: 'same-name', workspace_id: 'workspace-a' }, '/developer/coverage')).toBe(
      '/design/workspaces/workspace-a/projects/same-name/developer/coverage',
    )
    expect(projectPath({ id: 'same-name', workspace_id: 'workspace-b' }, '/developer/coverage')).toBe(
      '/design/workspaces/workspace-b/projects/same-name/developer/coverage',
    )
  })

  it('falls back to legacy project-only URLs only when workspace identity is unavailable', () => {
    expect(projectPathFromParts('same-name', null, '/pm')).toBe('/design/projects/same-name/pm')
    expect(legacyProjectPath('same-name', '/pm')).toBe('/design/projects/same-name/pm')
  })

  it('normalizes suffixes and exposes the canonical prefix', () => {
    expect(workspaceProjectPathPrefix('workspace-a', 'project-a')).toBe(
      '/design/workspaces/workspace-a/projects/project-a',
    )
    expect(projectPathFromParts('project-a', 'workspace-a', 'pm')).toBe(
      '/design/workspaces/workspace-a/projects/project-a/pm',
    )
    expect(projectPathFromParts('project a', 'workspace a', '/pm')).toBe(
      '/design/workspaces/workspace%20a/projects/project%20a/pm',
    )
  })

  it('canonicalizes legacy project URLs using the project workspace', () => {
    expect(isLegacyProjectPath('/design/projects/project-a/developer/coverage')).toBe(true)
    expect(
      canonicalProjectPathForSuffix(
        { id: 'project-a', workspace_id: 'workspace-a' },
        '/design/projects/project-a/developer/coverage',
      ),
    ).toBe('/design/workspaces/workspace-a/projects/project-a/developer/coverage')
  })
})
