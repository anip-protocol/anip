import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { buildProjectIssueIndex } from './project-issues'
import { projectStore } from './project-store'

export function useProjectIssue(issueKey: MaybeRefOrGetter<string>) {
  const issueIndex = computed(() => buildProjectIssueIndex({
    project: projectStore.activeProject,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: projectStore.artifacts.requirements,
    scenarios: projectStore.artifacts.scenarios,
    documents: projectStore.artifacts.documents,
    shapes: projectStore.artifacts.shapes,
  }))

  return computed(() => issueIndex.value[toValue(issueKey)])
}
