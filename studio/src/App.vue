<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { store } from './store'
import { fetchDiscovery } from './api'
import { syncStudioAnipBaseUrl } from './anip'
import { checkDbAvailable, clearProject, loadProject, projectStore, setActiveWorkspace } from './design/project-store'
import { requestConfirmation } from './design/confirm'
import { buildProjectIssueIndex } from './design/project-issues'
import { productDesignGate } from './design/project-workflow'
import {
  developerDefinitionMatchesCurrentContext,
  findDeveloperDefinitionArtifact,
} from './design/developer-definition'
import {
  findLatestProductDesignRevisionArtifact,
  productDesignSourceHash,
  type ProductDesignRevisionData,
} from './design/product-design'
import {
  developerBaselineMatchesCurrentContext,
  findDeveloperBaselineArtifact,
} from './design/traceability'
import type { DeveloperBaselineData, DeveloperDefinitionData } from './design/project-types'
import StudioSettingsDialog from './design/components/StudioAssistantConfigDialog.vue'
import StudioConfirmDialog from './design/components/StudioConfirmDialog.vue'
import { setStudioTimeDisplayMode, studioTimePreferences } from './design/time'
import { STUDIO_PROTOCOL_VERSION, STUDIO_VERSION_LABEL } from './version'

const router = useRouter()
const route = useRoute()

const urlInput = ref('')
const connecting = ref(false)
const settingsOpen = ref(false)

const inspectOnly = !!import.meta.env.VITE_INSPECT_ONLY

type StudioMode = 'home' | 'inspect' | 'design'

const activeMode = computed<StudioMode>(() => {
  const path = route.path
  if (path.startsWith('/inspect')) return 'inspect'
  if (path.startsWith('/design') || path.startsWith('/developer') || path.startsWith('/data-access')) return 'design'
  return 'home'
})

const inspectNavItems = [
  { name: 'discovery', label: 'Discovery', icon: '\u{1F50D}', path: '/inspect/discovery' },
  { name: 'manifest', label: 'Manifest', icon: '\u{1F4CB}', path: '/inspect/manifest' },
  { name: 'jwks', label: 'JWKS', icon: '\u{1F511}', path: '/inspect/jwks' },
  { name: 'audit', label: 'Audit', icon: '\u{1F4CA}', path: '/inspect/audit' },
  { name: 'approvals', label: 'Approvals', icon: '\u2714', path: '/inspect/approvals' },
  { name: 'checkpoints', label: 'Checkpoints', icon: '\u2713', path: '/inspect/checkpoints' },
  { name: 'invoke', label: 'Invoke', icon: '\u26A1', path: '/inspect/invoke' },
]

type DesignNavItem = {
  name: string
  label: string
  icon: string
  path: string
  child?: boolean
  staticLabel?: boolean
  groupHeader?: boolean
  lane?: 'product' | 'developer'
  modeSwitch?: boolean
  projectMode?: boolean
  surfaceRole?: string
}

type DesignNavGroup = {
  key: string
  heading: string | null
  items: DesignNavItem[]
}

type DesignLane = 'product' | 'developer'

const designLaneMemory = ref<Record<string, DesignLane>>({})

function getProjectLane(path: string): DesignLane | null {
  if (/^\/design\/projects\/[^/]+\/developer(?:\/|$)/.test(path)) return 'developer'
  if (/^\/design\/projects\/[^/]+\/fronting(?:\/|$)/.test(path)) return 'developer'
  if (
    /^\/design\/projects\/[^/]+\/(?:source-docs|first-draft|pm|product-summary|actor-model|business-areas|permission-intent|requirements|scenarios|shapes|non-goals|success-criteria|pm-artifacts|pm-review|proposals)(?:\/|$)/.test(path)
  ) {
    return 'product'
  }
  return null
}

const currentProjectLane = computed<DesignLane | null>(() => {
  const pid = projectStore.activeProject?.id
  const explicitLane = getProjectLane(route.path)
  if (explicitLane) return explicitLane
  if (/^\/design\/projects\/[^/]+\/verification(?:\/|$)/.test(route.path)) return null
  if (route.name === 'project-dashboard' && route.query.view === 'product') return 'product'
  if (route.name === 'project-dashboard' && route.query.view === 'developer') return 'developer'
  if (route.name === 'project-dashboard' && route.query.view === 'overview') return null
  if (pid && designLaneMemory.value[pid]) return designLaneMemory.value[pid]
  return null
})

watch(
  () => [route.path, route.query.view, projectStore.activeProject?.id] as const,
  ([path, view, projectId]) => {
    if (!projectId) return
    if (path === `/design/projects/${projectId}` && (view === 'product' || view === 'developer')) {
      designLaneMemory.value = {
        ...designLaneMemory.value,
        [projectId]: view,
      }
      return
    }
    const lane = getProjectLane(path)
    if (!lane || !projectId) return
    designLaneMemory.value = {
      ...designLaneMemory.value,
      [projectId]: lane,
    }
  },
  { immediate: true },
)

const designNavItems = computed<DesignNavItem[]>(() => {
  const project = projectStore.activeProject
  const items: DesignNavItem[] = []
  if (project) {
    const pid = project.id
    const activeLane = currentProjectLane.value
    const hasShapes = projectStore.artifacts.shapes.length > 0
    const isGovernedFrontingProject = project.project_type === 'governed_service_project'
    items.push({
      name: 'project-product-design',
      label: 'Product Design',
      icon: '\u2022',
      path: `/design/projects/${pid}`,
      child: true,
      lane: 'product',
      modeSwitch: true,
      projectMode: true,
    })
    if (activeLane === 'product') {
      items.push({
        name: 'product-group-reference',
        label: 'Reference',
        icon: '',
        path: '',
        child: true,
        lane: 'product',
        staticLabel: true,
        groupHeader: true,
      })
      items.push({
        name: 'project-source-docs',
        label: 'Source Docs',
        icon: '\u2022',
        path: `/design/projects/${pid}/source-docs`,
        child: true,
        lane: 'product',
        surfaceRole: 'Reference',
      })
      items.push({
        name: 'project-product-ai-assistant',
        label: 'Product Design AI Assistant',
        icon: '\u2022',
        path: `/design/projects/${pid}/pm/assistant`,
        child: true,
        lane: 'product',
        surfaceRole: 'Draft',
      })
    }
    if (projectStore.pendingIntentDraft && activeLane === 'product') {
      items.push({
        name: 'first-draft-review',
        label: 'First Draft Review',
        icon: '\u2022',
        path: `/design/projects/${pid}/first-draft`,
        child: true,
        lane: 'product',
        surfaceRole: 'Review',
      })
    }
    if (activeLane === 'product') {
      items.push({
        name: 'product-group-author',
        label: 'Author Product Design',
        icon: '',
        path: '',
        child: true,
        lane: 'product',
        staticLabel: true,
        groupHeader: true,
      })
      items.push(
        {
          name: 'project-pm',
          label: 'Product Overview',
          icon: '\u2022',
          path: `/design/projects/${pid}/pm`,
          child: true,
          lane: 'product',
          surfaceRole: 'Review',
        },
        {
          name: 'project-product-diagrams',
          label: 'Product Diagrams',
          icon: '\u2022',
          path: `/design/projects/${pid}/pm/diagrams`,
          child: true,
          lane: 'product',
          surfaceRole: 'Map',
        },
        {
          name: 'project-product-summary',
          label: 'Business Summary',
          icon: '\u2022',
          path: `/design/projects/${pid}/product-summary`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-actor-model',
          label: 'Actor Model',
          icon: '\u2022',
          path: `/design/projects/${pid}/actor-model`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-business-areas',
          label: 'Business Areas',
          icon: '\u2022',
          path: `/design/projects/${pid}/business-areas`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-permission-intent',
          label: 'Permission Intent',
          icon: '\u2022',
          path: `/design/projects/${pid}/permission-intent`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-requirements-list',
          label: 'What Matters',
          icon: '\u2022',
          path: `/design/projects/${pid}/requirements`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-scenarios-list',
          label: 'Real Situations',
          icon: '\u2022',
          path: `/design/projects/${pid}/scenarios`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-shapes',
          label: 'Service Design',
          icon: '\u2022',
          path: `/design/projects/${pid}/shapes`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-non-goals',
          label: 'Non-Goals',
          icon: '\u2022',
          path: `/design/projects/${pid}/non-goals`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'project-success-criteria',
          label: 'Success Criteria',
          icon: '\u2022',
          path: `/design/projects/${pid}/success-criteria`,
          child: true,
          lane: 'product',
          surfaceRole: 'Author',
        },
        {
          name: 'product-group-review',
          label: 'Review & Sign Off',
          icon: '',
          path: '',
          child: true,
          lane: 'product',
          staticLabel: true,
          groupHeader: true,
        },
        {
          name: 'project-pm-artifacts',
          label: 'PM Artifacts',
          icon: '\u2022',
          path: `/design/projects/${pid}/pm-artifacts`,
          child: true,
          lane: 'product',
          surfaceRole: 'Record',
        },
        {
          name: 'project-pm-review',
          label: 'PM Review',
          icon: '\u2022',
          path: `/design/projects/${pid}/pm-review`,
          child: true,
          lane: 'product',
          surfaceRole: 'Sign Off',
        },
      )
      if (!hasShapes && projectStore.activeProposalId) {
        items.push({
          name: 'proposal',
          label: 'Legacy Approach',
          icon: '\u2022',
          path: `/design/projects/${pid}/proposals/${projectStore.activeProposalId}`,
          child: true,
          lane: 'product',
          surfaceRole: 'Legacy',
        })
      }
    }
    items.push(
      {
        name: 'project-developer-design',
        label: 'Developer Design',
        icon: '\u2022',
        path: `/design/projects/${pid}`,
        child: true,
        lane: 'developer',
        modeSwitch: true,
        projectMode: true,
      },
    )
    if (activeLane === 'developer') {
      items.push({
        name: 'developer-group-baseline',
        label: 'Baseline & Review',
        icon: '',
        path: '',
        child: true,
        lane: 'developer',
        staticLabel: true,
        groupHeader: true,
      })
      items.push(
        {
          name: 'project-developer-home',
          label: 'Developer Overview',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Review',
        },
        {
          name: 'project-developer-diagrams',
          label: 'Developer Diagrams',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/diagrams`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Map',
        },
        {
          name: 'project-developer-ai-assistant',
          label: 'Developer Design AI Assistant',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/assistant`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Draft',
        },
        {
          name: 'project-developer-handoff',
          label: 'Locked Product Handoff',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/handoff`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Baseline',
        },
        {
          name: 'project-developer-source-docs',
          label: 'Developer Source Docs',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/source-docs`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Evidence',
        },
        ...(isGovernedFrontingProject
          ? [
              {
                name: 'project-fronting-express',
                label: 'Govern API / MCP',
                icon: '\u2022',
                path: `/design/projects/${pid}/fronting`,
                child: true,
                lane: 'developer',
                surfaceRole: 'Map',
              } satisfies DesignNavItem,
            ]
          : []),
        {
          name: 'developer-group-formalize',
          label: 'Formalize Contract',
          icon: '',
          path: '',
          child: true,
          lane: 'developer',
          staticLabel: true,
          groupHeader: true,
        },
        ...(isGovernedFrontingProject
          ? [
              {
                name: 'project-integration-fronting',
                label: 'API/MCP Mappings',
                icon: '\u2022',
                path: `/design/projects/${pid}/developer/integration-fronting`,
                child: true,
                lane: 'developer',
                surfaceRole: 'Formalize',
              } satisfies DesignNavItem,
            ]
          : []),
        {
          name: 'project-developer-service-formalization',
          label: 'Service Formalization',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/service-formalization`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-capability-formalization',
          label: 'Capability Formalization',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/capability-formalization`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-governance-bindings',
          label: 'Roles & Access',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/governance-bindings`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-audit-lineage',
          label: 'Audit & Lineage',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/audit-lineage`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-scenario-formalization',
          label: 'Scenario Coverage Intent',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/scenario-formalization`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-scenario-execution-semantics',
          label: 'Scenario Execution Semantics',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/scenario-execution-semantics`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-generation-settings',
          label: 'Generation Settings',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/generation-settings`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'project-developer-verification-expectations',
          label: 'Evidence & Verification Plan',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/verification-expectations`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Formalize',
        },
        {
          name: 'developer-group-review',
          label: 'Review Contract',
          icon: '',
          path: '',
          child: true,
          lane: 'developer',
          staticLabel: true,
          groupHeader: true,
        },
        {
          name: 'project-developer-coverage',
          label: 'Coverage Mapping',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/coverage`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Review',
        },
        {
          name: 'project-developer-app-glue',
          label: 'Agent & App Glue',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/app-glue`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Review',
        },
        {
          name: 'project-developer-gaps',
          label: 'Consistency Gaps',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/gaps`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Evidence',
        },
        {
          name: 'project-developer-definition',
          label: 'Developer Definition',
          icon: '\u2022',
          path: `/design/projects/${pid}/developer/definition`,
          child: true,
          lane: 'developer',
          surfaceRole: 'Compile',
        },
      )
    }
    items.push({
      name: 'project-revisions',
      label: 'Revision History',
      icon: '\u2022',
      path: `/design/projects/${pid}/revisions`,
      child: true,
      projectMode: true,
      surfaceRole: 'Evidence',
    })
    items.push({
      name: 'project-template-export',
      label: 'Create Template',
      icon: '\u2022',
      path: `/design/projects/${pid}/templates/export`,
      child: true,
      projectMode: true,
      surfaceRole: 'Share',
    })
    items.push({
      name: 'project-verification',
      label: 'Verification',
      icon: '\u2022',
      path: `/design/projects/${pid}/verification`,
      child: true,
      projectMode: true,
      surfaceRole: 'Evidence',
    })
  }
  return items
})

type HeaderContextLink = {
  key: string
  label: string
  path: string
  current?: boolean
}

type HeaderRevisionBadge = {
  key: string
  label: string
  title: string
  path: string
  status: 'current' | 'draft' | 'stale'
}

const headerContextLinks = computed<HeaderContextLink[]>(() => {
  if (activeMode.value !== 'design') return []
  const links: HeaderContextLink[] = [{ key: 'workspaces', label: 'Workspaces', path: '/design' }]
  const workspace = projectStore.activeWorkspace
  if (workspace) {
    links.push({
      key: 'workspace',
      label: workspace.name,
      path: `/design/workspaces/${workspace.id}`,
    })
  }
  const project = projectStore.activeProject
  if (project) {
    links.push({
      key: 'project',
      label: project.name,
      path: `/design/projects/${project.id}`,
      current: true,
    })
  }
  return links
})

const currentRequirementsForLineage = computed(() =>
  projectStore.artifacts.requirements.find((item) => item.role === 'primary')
  ?? projectStore.artifacts.requirements[0]
  ?? null,
)

const currentShapeForLineage = computed(() =>
  projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId)
  ?? (projectStore.artifacts.shapes.length === 1 ? projectStore.artifacts.shapes[0] : null)
  ?? projectStore.artifacts.shapes[0]
  ?? null,
)

const baselineForLineage = computed(() =>
  (findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts)?.data as DeveloperBaselineData | undefined) ?? null,
)

const developerDefinitionForLineage = computed(() =>
  (findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts)?.data as DeveloperDefinitionData | undefined) ?? null,
)

const headerRevisionBadges = computed<HeaderRevisionBadge[]>(() => {
  if (activeMode.value !== 'design') return []
  const project = projectStore.activeProject
  if (!project) return []

  const badges: HeaderRevisionBadge[] = []
  const productRevision = findLatestProductDesignRevisionArtifact(projectStore.artifacts.pmArtifacts)?.data as ProductDesignRevisionData | undefined
  const currentProductHash = productDesignSourceHash(projectStore.artifacts.pmArtifacts)
  const baseline = baselineForLineage.value
  const baselineAligned = developerBaselineMatchesCurrentContext({
    baseline,
    requirements: currentRequirementsForLineage.value,
    scenarios: projectStore.artifacts.scenarios,
    shape: currentShapeForLineage.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
  })

  if (productRevision?.revision_number) {
    const productDraftAhead = productRevision.product_design_hash !== currentProductHash
    const baselinePinnedToLatest = baseline?.source_inputs.product_revision_artifact_id === productRevision.revision_artifact_id
    badges.push({
      key: 'product-revision',
      label: productDraftAhead
        ? `Product draft (r${productRevision.revision_number} base)`
        : `Product r${productRevision.revision_number}`,
      title: [
        `Product Revision ${productRevision.revision_number}`,
        `Artifact: ${productRevision.revision_artifact_id}`,
        productDraftAhead ? 'Working Product Design has changed since this revision.' : 'Working Product Design matches this revision.',
        baselinePinnedToLatest ? 'Developer Baseline is pinned to this revision.' : 'Developer Baseline is not pinned to the latest Product Revision.',
      ].join('\n'),
      path: `/design/projects/${project.id}`,
      status: productDraftAhead ? 'draft' : baselineAligned ? 'current' : 'stale',
    })
  } else if (currentProductHash) {
    badges.push({
      key: 'product-revision',
      label: 'Product draft',
      title: 'No Product Revision has been locked yet. Lock Developer Baseline to create Product Revision 1.',
      path: `/design/projects/${project.id}`,
      status: 'draft',
    })
  }

  const developerDefinition = developerDefinitionForLineage.value
  const savedRevision = developerDefinition?.saved_revision ?? null
  if (savedRevision?.revision_number) {
    const developerAligned = developerDefinitionMatchesCurrentContext({
      definition: developerDefinition,
      baseline,
      requirements: currentRequirementsForLineage.value,
      scenarios: projectStore.artifacts.scenarios,
      shape: currentShapeForLineage.value,
    })
    badges.push({
      key: 'developer-revision',
      label: `Dev r${savedRevision.revision_number}`,
      title: [
        `Developer Revision ${savedRevision.revision_number}`,
        `Artifact: ${savedRevision.revision_artifact_id}`,
        savedRevision.previous_revision_artifact_id ? `Previous: ${savedRevision.previous_revision_artifact_id}` : 'Previous: none',
        developerAligned ? 'Developer Revision matches the active baseline.' : 'Developer Revision is stale against the active baseline.',
      ].join('\n'),
      path: `/design/projects/${project.id}/developer`,
      status: developerAligned ? 'current' : 'stale',
    })
  } else if (baseline) {
    badges.push({
      key: 'developer-revision',
      label: 'Dev draft',
      title: 'Developer Baseline is locked, but no immutable Developer Revision has been saved yet.',
      path: `/design/projects/${project.id}/developer/definition`,
      status: 'draft',
    })
  }

  return badges
})

const designNavGroups = computed<DesignNavGroup[]>(() => {
  const groups: DesignNavGroup[] = []
  let current: DesignNavGroup = { key: 'primary', heading: null, items: [] }

  for (const item of designNavItems.value) {
    if (item.groupHeader) {
      if (current.items.length) groups.push(current)
      current = {
        key: item.name,
        heading: item.label,
        items: [],
      }
      continue
    }
    current.items.push(item)
  }

  if (current.items.length) groups.push(current)
  return groups
})

const activeRoute = computed(() => route.name as string)
const timeDisplayMode = computed({
  get: () => studioTimePreferences.mode,
  set: (value: string) => {
    setStudioTimeDisplayMode(value === 'utc' ? 'utc' : 'local')
  },
})
const readOnlyHeaderReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason || 'Studio is running in read-only mode.',
)
const showReadOnlyHeaderBadge = computed(() => projectStore.runtimeStatus?.read_only_mode === true)

const showSidebar = computed(() => activeMode.value !== 'home')
const showConnectBar = computed(() => activeMode.value === 'inspect')
const designIssueIndex = computed(() =>
  buildProjectIssueIndex({
    project: projectStore.activeProject,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: projectStore.artifacts.requirements,
    scenarios: projectStore.artifacts.scenarios,
    documents: projectStore.artifacts.documents,
    shapes: projectStore.artifacts.shapes,
  }),
)
const productGate = computed(() =>
  productDesignGate({
    project: projectStore.activeProject,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: projectStore.artifacts.requirements,
    scenarios: projectStore.artifacts.scenarios,
    documents: projectStore.artifacts.documents,
    shapes: projectStore.artifacts.shapes,
  }),
)

watch(
  () => [route.path, productGate.value.ready, projectStore.activeProject?.id, projectStore.loading] as const,
  ([path, productReady, projectId, loading]) => {
    if (!projectId || loading || productReady) return
    if (getProjectLane(path) !== 'developer') return
    router.replace(`/design/projects/${projectId}/pm`)
  },
  { immediate: true },
)

function designItemIssue(name: string) {
  return designIssueIndex.value[name]
}

function navigate(path: string) {
  router.push(path)
}

async function maybeConfirmProjectClose(targetPath: string): Promise<boolean> {
  const activeProject = projectStore.activeProject
  if (!activeProject || !route.path.startsWith(`/design/projects/${activeProject.id}`)) return true

  if (targetPath === '/design') {
    const confirmed = await requestConfirmation({
      title: 'Leave the current project?',
      message: 'This will close the current project view and return to the workspace list.',
      confirmLabel: 'Open Workspaces',
      cancelLabel: 'Stay Here',
      tone: 'neutral',
    })
    if (!confirmed) return false
    clearProject()
    return true
  }

  const activeWorkspace = projectStore.activeWorkspace
  if (activeWorkspace && targetPath === `/design/workspaces/${activeWorkspace.id}`) {
    const confirmed = await requestConfirmation({
      title: 'Leave the current project?',
      message: 'This will close the current project view and return to the project list for this workspace.',
      confirmLabel: 'Open Workspace Projects',
      cancelLabel: 'Stay Here',
      tone: 'neutral',
    })
    if (!confirmed) return false
    clearProject()
    setActiveWorkspace(activeWorkspace)
    return true
  }

  return true
}

async function handleHeaderContextNavigation(link: HeaderContextLink) {
  if (link.current) return
  const canProceed = await maybeConfirmProjectClose(link.path)
  if (!canProceed) return
  navigate(link.path)
}

function isDesignItemActive(item: DesignNavItem): boolean {
  if (item.staticLabel) return false
  if (item.modeSwitch) return false
  if (item.path.includes('#')) {
    const [base, hash] = item.path.split('#')
    return route.path === base && route.hash === `#${hash}`
  }
  if (item.name === 'project-dashboard') {
    return route.path === item.path || route.path.startsWith(`${item.path}/`) || activeRoute.value === 'project-dashboard'
  }
  if (item.name === 'project-product-design') {
    return currentProjectLane.value === 'product' && !!projectStore.activeProject
  }
  if (item.name === 'project-developer-design') {
    return currentProjectLane.value === 'developer' && !!projectStore.activeProject
  }
  if (item.name === 'project-developer-home') {
    return route.path === item.path || activeRoute.value === item.name
  }
  if (route.path === item.path || activeRoute.value === item.name) return true
  return [
    'project-requirements-list',
    'project-scenarios-list',
    'project-shapes',
    'project-pm-artifacts',
  ].includes(item.name) && route.path.startsWith(`${item.path}/`)
}

function isDesignModeSwitchOpen(item: DesignNavItem): boolean {
  if (!item.modeSwitch || !item.lane) return false
  return currentProjectLane.value === item.lane
}

function renderDesignNavIcon(item: DesignNavItem): string {
  return item.icon
}

async function handleDesignNavigation(item: DesignNavItem) {
  if (item.staticLabel) return
  if (item.name === 'workspace-list' || item.name === 'workspace-projects') {
    const canProceed = await maybeConfirmProjectClose(item.path)
    if (!canProceed) return
  }
  const activeProject = projectStore.activeProject
  if (activeProject && item.lane === 'developer' && !productGate.value.ready) {
    router.push(`/design/projects/${activeProject.id}/pm`)
    return
  }
  if (item.modeSwitch && activeProject && item.lane) {
    router.push({
      path: `/design/projects/${activeProject.id}`,
      query: { view: item.lane },
    })
    return
  }
  navigate(item.path)
}

function switchMode(mode: 'inspect' | 'design') {
  if (mode === 'inspect') {
    router.push('/inspect/discovery')
  } else {
    const pid = projectStore.activeProject?.id
    router.push(pid ? `/design/projects/${pid}` : '/design')
  }
}

async function connect() {
  const url = urlInput.value.replace(/\/+$/, '')
  if (!url) return

  connecting.value = true
  store.error = ''

  try {
    await fetchDiscovery(url)
    store.baseUrl = url
    store.connected = true
    syncStudioAnipBaseUrl(url)
  } catch (e: unknown) {
    store.error = e instanceof Error ? e.message : 'Connection failed'
  } finally {
    connecting.value = false
  }
}

function disconnect() {
  store.baseUrl = ''
  store.connected = false
  store.error = ''
  store.serviceId = ''
  syncStudioAnipBaseUrl('')
  urlInput.value = ''
}

async function handleSettingsSaved() {
  settingsOpen.value = false
  if (projectStore.activeProject?.id) {
    await loadProject(projectStore.activeProject.id)
    return
  }
  await checkDbAvailable()
}
</script>

<template>
  <div class="studio-app" :class="{ 'no-sidebar': !showSidebar }">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <div class="brand" @click="navigate('/')" style="cursor: pointer;">
          <span class="brand-logo">&#x25C6;</span>
          <span class="brand-name">ANIP <span class="brand-accent">Studio</span></span>
        </div>
        <!-- Mode switcher (hidden in Inspect-only embedded builds) -->
        <div class="mode-switcher" v-if="!inspectOnly && activeMode !== 'home'">
          <button
            class="mode-tab"
            :class="{ active: activeMode === 'inspect' }"
            @click="switchMode('inspect')"
          >Invoke & Inspect</button>
          <button
            class="mode-tab"
            :class="{ active: activeMode === 'design' }"
            @click="switchMode('design')"
          >Design</button>
        </div>
        <div v-if="headerContextLinks.length" class="header-context">
          <button
            v-for="(link, index) in headerContextLinks"
            :key="link.key"
            class="header-context-link"
            :class="{ 'header-context-link-current': link.current }"
            @click="handleHeaderContextNavigation(link)"
          >
            <span v-if="index > 0" class="header-context-separator">/</span>
            <span class="header-context-label">{{ link.label }}</span>
          </button>
          <div v-if="headerRevisionBadges.length" class="header-revision-badges" aria-label="Active revision lineage">
            <button
              v-for="badge in headerRevisionBadges"
              :key="badge.key"
              class="header-revision-badge"
              :class="`header-revision-badge-${badge.status}`"
              type="button"
              :title="badge.title"
              @click="navigate(badge.path)"
            >
              {{ badge.label }}
            </button>
          </div>
        </div>
      </div>

      <div class="header-center" v-if="showConnectBar">
        <div v-if="store.connected" class="connected-badge" @click="disconnect">
          <span class="status-dot connected"></span>
          <span class="connected-url">{{ store.baseUrl }}</span>
          <span class="disconnect-hint">&times;</span>
        </div>
        <div v-else class="connect-bar">
          <input
            v-model="urlInput"
            type="text"
            class="url-input"
            placeholder="https://your-service.example.com"
            @keyup.enter="connect"
            :disabled="connecting"
          />
          <button class="connect-btn" @click="connect" :disabled="connecting || !urlInput">
            {{ connecting ? 'Connecting...' : 'Connect' }}
          </button>
        </div>
      </div>
      <div class="header-center" v-else></div>

      <div class="header-right">
        <span
          v-if="showReadOnlyHeaderBadge"
          class="header-readonly-badge"
          :title="readOnlyHeaderReason"
        >
          Read-only mode
        </span>
        <label v-if="showSidebar" class="header-time-pref">
          <span class="header-time-pref-label">Time</span>
          <select v-model="timeDisplayMode" class="header-time-pref-select">
            <option value="local">Local</option>
            <option value="utc">UTC</option>
          </select>
        </label>
        <button
          v-if="activeMode === 'design'"
          class="header-config-btn"
          type="button"
          @click="settingsOpen = true"
        >
          Settings
        </button>
        <span v-if="showConnectBar && store.error" class="error-badge" :title="store.error">
          <span class="status-dot error"></span>
          Error
        </span>
        <span v-else-if="showConnectBar && store.connected" class="status-badge">
          <span class="status-dot connected"></span>
          Connected
        </span>
        <span v-else-if="showConnectBar" class="status-badge muted">
          <span class="status-dot idle"></span>
          Not connected
        </span>
      </div>
    </header>

    <!-- Body -->
    <div class="body">
      <!-- Sidebar (Inspect or Design) -->
      <nav v-if="showSidebar" class="sidebar">
        <!-- Inspect sidebar -->
        <ul v-if="activeMode === 'inspect'" class="nav-list">
          <li
            v-for="item in inspectNavItems"
            :key="item.name"
            class="nav-item"
            :class="{ active: activeRoute === item.name }"
            @click="navigate(item.path)"
            :title="item.label"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
        <!-- Design sidebar -->
        <div v-else-if="activeMode === 'design'" class="nav-groups">
          <section
            v-for="group in designNavGroups"
            :key="group.key"
            class="nav-group"
          >
            <h3 v-if="group.heading" class="nav-group-heading">{{ group.heading }}</h3>
            <ul class="nav-list">
              <li
                v-for="item in group.items"
                :key="item.name"
                class="nav-item"
                :class="{
                  active: isDesignItemActive(item),
                  'nav-item-child': item.child,
                  'nav-item-static': item.staticLabel,
                  'nav-item-project-mode': item.projectMode,
                  'nav-item-project-mode-open': isDesignModeSwitchOpen(item),
                }"
                @click="handleDesignNavigation(item)"
                :title="item.label"
              >
                <span class="nav-icon">{{ renderDesignNavIcon(item) }}</span>
                <span class="nav-label">{{ item.label }}</span>
                <span
                  v-if="!item.staticLabel && designItemIssue(item.name)"
                  class="nav-issue-badge"
                  :class="`nav-issue-${designItemIssue(item.name)?.severity}`"
                  :title="designItemIssue(item.name)?.messages.join('\n')"
                >
                  {{ designItemIssue(item.name)?.count }}
                </span>
              </li>
            </ul>
          </section>
        </div>
        <div class="sidebar-footer">
          <span class="version">{{ STUDIO_VERSION_LABEL }}</span>
          <span class="version version-protocol">{{ STUDIO_PROTOCOL_VERSION }}</span>
          <a class="footer-link" href="https://anip.dev" target="_blank" rel="noreferrer">anip.dev</a>
        </div>
      </nav>

      <!-- Main Content -->
      <main class="content">
        <div v-if="activeMode === 'inspect' && !store.connected" class="welcome">
          <div class="welcome-icon">&#x25C6;</div>
          <h2 class="welcome-title">Connect to an ANIP capability service</h2>
          <p class="welcome-text">Enter a service URL to inspect its discovery document, manifest, capabilities, audit traces, and runtime evidence.</p>
          <div class="welcome-connect">
            <input
              v-model="urlInput"
              type="text"
              class="welcome-input"
              placeholder="https://your-service.example.com"
              @keyup.enter="connect"
              :disabled="connecting"
            />
            <button class="connect-btn welcome-btn" @click="connect" :disabled="connecting || !urlInput">
              {{ connecting ? 'Connecting...' : 'Connect' }}
            </button>
          </div>
          <p v-if="store.error" class="welcome-error">{{ store.error }}</p>
          <div class="welcome-examples">
            <span class="welcome-examples-label">Try a playground service:</span>
            <button class="example-link" @click="urlInput = 'https://travel.playground.anip.dev'; connect()">Travel</button>
            <button class="example-link" @click="urlInput = 'https://finance.playground.anip.dev'; connect()">Finance</button>
            <button class="example-link" @click="urlInput = 'https://devops.playground.anip.dev'; connect()">DevOps</button>
          </div>
        </div>
        <router-view v-else />
      </main>
    </div>
  </div>
  <StudioConfirmDialog />
  <StudioSettingsDialog
    :open="settingsOpen"
    @close="settingsOpen = false"
    @saved="handleSettingsSaved"
  />
</template>

<style scoped>
/* ── Layout ── */
.studio-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-app);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  --scrollbar-size: 10px;
  --scrollbar-track: rgba(15, 23, 42, 0.14);
  --scrollbar-thumb: rgba(100, 116, 139, 0.48);
  --scrollbar-thumb-hover: rgba(96, 165, 250, 0.58);
  --scrollbar-thumb-active: rgba(59, 130, 246, 0.72);
  --scrollbar-edge: rgba(148, 163, 184, 0.12);
}

.studio-app :deep(*) {
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

.studio-app :deep(*::-webkit-scrollbar) {
  width: var(--scrollbar-size);
  height: var(--scrollbar-size);
}

.studio-app :deep(*::-webkit-scrollbar-track) {
  background: var(--scrollbar-track);
  border-radius: 999px;
}

.studio-app :deep(*::-webkit-scrollbar-thumb) {
  background:
    linear-gradient(180deg, rgba(148, 163, 184, 0.32), var(--scrollbar-thumb));
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.studio-app :deep(*::-webkit-scrollbar-thumb:hover) {
  background:
    linear-gradient(180deg, rgba(191, 219, 254, 0.36), var(--scrollbar-thumb-hover));
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.studio-app :deep(*::-webkit-scrollbar-thumb:active) {
  background:
    linear-gradient(180deg, rgba(219, 234, 254, 0.44), var(--scrollbar-thumb-active));
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.studio-app :deep(*::-webkit-scrollbar-corner) {
  background: transparent;
}

/* ── Header ── */
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 56px;
  padding: 0 20px;
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 180px;
  min-width: 0;
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
  font-size: 10px;
}

.sidebar-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
  border-color: var(--text-muted);
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}

.brand-logo {
  font-size: 18px;
  color: var(--accent);
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--text-primary);
}

.brand-accent {
  color: var(--accent);
  font-weight: 500;
}

/* ── Mode Switcher ── */
.mode-switcher {
  display: flex;
  margin-left: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.header-context {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  margin-left: 4px;
  padding-left: 12px;
  border-left: 1px solid rgba(71, 85, 105, 0.42);
  overflow: hidden;
}

.header-context-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 0;
  background: transparent;
  border: none;
  color: rgba(148, 163, 184, 0.82);
  cursor: pointer;
  transition: color var(--transition);
}

.header-context-link:hover {
  color: var(--text-primary);
}

.header-context-link-current {
  color: rgba(226, 232, 240, 0.96);
}

.header-context-separator {
  color: rgba(100, 116, 139, 0.8);
  flex-shrink: 0;
}

.header-context-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
}

.header-revision-badges {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  margin-left: 8px;
  padding-left: 10px;
  border-left: 1px solid rgba(71, 85, 105, 0.42);
}

.header-revision-badge {
  display: inline-flex;
  align-items: center;
  max-width: 160px;
  height: 22px;
  padding: 0 8px;
  border: 1px solid rgba(71, 85, 105, 0.78);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: rgba(226, 232, 240, 0.92);
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: border-color var(--transition), background var(--transition), color var(--transition);
}

.header-revision-badge:hover {
  border-color: rgba(148, 163, 184, 0.9);
  background: rgba(30, 41, 59, 0.9);
  color: var(--text-primary);
}

.header-revision-badge-current {
  border-color: rgba(52, 211, 153, 0.46);
  color: rgba(187, 247, 208, 0.96);
}

.header-revision-badge-draft {
  border-color: rgba(251, 191, 36, 0.5);
  color: rgba(254, 240, 138, 0.96);
}

.header-revision-badge-stale {
  border-color: rgba(248, 113, 113, 0.54);
  color: rgba(254, 202, 202, 0.96);
}

.mode-tab {
  padding: 4px 16px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
}

.mode-tab:not(:last-child) {
  border-right: 1px solid var(--border);
}

.mode-tab:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.mode-tab.active {
  color: var(--accent);
  background: var(--accent-glow);
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 560px;
  margin: 0 auto;
}

.connect-bar {
  display: flex;
  width: 100%;
  gap: 8px;
}

.url-input {
  flex: 1;
  height: 36px;
  padding: 0 14px;
  background: var(--bg-input);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.url-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

.url-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.connect-btn {
  height: 36px;
  padding: 0 20px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
  white-space: nowrap;
}

.connect-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.connect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.connected-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  max-width: 100%;
}

.connected-badge:hover {
  border-color: var(--error);
}

.connected-badge:hover .disconnect-hint {
  opacity: 1;
  color: var(--error);
}

.connected-url {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disconnect-hint {
  font-size: 16px;
  color: var(--text-muted);
  opacity: 0;
  transition: all var(--transition);
  margin-left: 4px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 140px;
  justify-content: flex-end;
}

.header-time-pref {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-time-pref-label {
  font-size: 12px;
  color: var(--text-muted);
}

.header-time-pref-select {
  min-height: 30px;
  padding: 0 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 12px;
}

.header-readonly-badge {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px solid rgba(245, 158, 11, 0.44);
  border-radius: var(--radius-sm);
  background: rgba(245, 158, 11, 0.12);
  color: #f8d08b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.header-config-btn {
  min-height: 30px;
  padding: 0 12px;
  background: rgba(15, 23, 42, 0.82);
  border: 1px solid rgba(71, 85, 105, 0.78);
  border-radius: var(--radius-sm);
  color: rgba(226, 232, 240, 0.96);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition), color var(--transition);
}

.header-config-btn:hover {
  background: rgba(30, 41, 59, 0.94);
  border-color: rgba(96, 165, 250, 0.78);
  color: #ffffff;
}

.status-badge,
.error-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 20px;
  background: var(--bg-input);
  border: 1px solid var(--border);
}

.status-badge.muted {
  color: var(--text-muted);
}

.error-badge {
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.connected {
  background: var(--success);
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.4);
}

.status-dot.idle {
  background: var(--text-muted);
}

.status-dot.error {
  background: var(--error);
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.4);
}

/* ── Body ── */
.body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Sidebar ── */
.sidebar {
  width: 220px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  box-shadow: inset -1px 0 0 var(--scrollbar-edge);
}

.nav-list {
  list-style: none;
  padding: 0 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.nav-group {
  padding-top: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.nav-group:first-child {
  padding-top: 0;
  border-top: none;
}

.nav-group-heading {
  margin: 0 18px 8px;
  color: rgba(148, 163, 184, 0.72);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  color: var(--text-secondary);
  white-space: normal;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--bg-active);
  color: var(--text-primary);
  box-shadow: inset 3px 0 0 var(--accent);
}

.nav-item-child {
  margin-left: 18px;
  padding-top: 8px;
  padding-bottom: 8px;
  color: var(--text-muted);
}

.nav-item-project-mode {
  margin: 4px 8px 10px;
  padding: 11px 14px;
  border: 1px solid rgba(71, 85, 105, 0.4);
  background: var(--surface-depth-card);
  color: rgba(148, 163, 184, 0.86);
  font-weight: 700;
  border-radius: 10px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

.nav-item-project-mode:hover {
  background: rgba(30, 41, 59, 0.48);
  border-color: rgba(100, 116, 139, 0.6);
  color: rgba(226, 232, 240, 0.96);
}

.nav-item-project-mode-open,
.nav-item-project-mode.active {
  border-color: rgba(96, 165, 250, 0.58);
  background:
    linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.96));
  color: #dbeafe;
  box-shadow:
    inset 0 1px 0 rgba(191, 219, 254, 0.08),
    0 0 0 1px rgba(59, 130, 246, 0.08);
}

.nav-item-project-mode .nav-icon {
  width: 16px;
  font-size: 12px;
  color: rgba(100, 116, 139, 0.92);
}

.nav-item-project-mode .nav-label {
  font-size: 14px;
  font-weight: 700;
}

.nav-item-project-mode-open .nav-icon,
.nav-item-project-mode.active .nav-icon {
  color: rgba(191, 219, 254, 0.96);
}

.nav-item-child .nav-icon {
  width: 16px;
  font-size: 12px;
}

.nav-item-child .nav-label {
  font-size: 13px;
  font-weight: 500;
}

.nav-item-static {
  cursor: default;
  color: var(--text-primary);
  font-weight: 600;
}

.nav-item-static:hover {
  background: transparent;
  color: var(--text-primary);
}

.nav-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
  line-height: 1.4;
}

.nav-label {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.nav-issue-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  flex-shrink: 0;
  border: 1px solid var(--surface-border-card);
}

.nav-issue-indicator {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex-shrink: 0;
  margin-top: 5px;
  border: 1px solid var(--surface-border-card);
}

.nav-issue-error {
  background: rgba(127, 29, 29, 0.28);
  border-color: rgba(248, 113, 113, 0.42);
  color: #fecaca;
}

.nav-issue-warning {
  background: rgba(120, 53, 15, 0.24);
  border-color: rgba(251, 191, 36, 0.36);
  color: #fde68a;
}

.sidebar-footer {
  margin-top: auto;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.version {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.version-protocol {
  margin-top: 2px;
  opacity: 0.85;
}

.footer-link {
  display: inline-block;
  margin-top: 8px;
  font-size: 11px;
  color: var(--accent);
  text-decoration: none;
}

.footer-link:hover {
  text-decoration: underline;
}

/* ── Content ── */
.content {
  flex: 1;
  background: var(--bg-content);
  overflow-y: auto;
}

/* The full hosted-preview explanation belongs at workspace entry points only.
   Project pages keep disabled controls plus the persistent header badge. */
:global(.readonly-banner),
:global(.revision-banner.readonly) {
  display: none !important;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .header-left {
    min-width: auto;
  }

  .brand-name {
    display: none;
  }

  .header-right {
    min-width: auto;
  }

  .header-time-pref-label {
    display: none;
  }

  .header-readonly-badge {
    padding: 0 8px;
    font-size: 11px;
  }

  .mode-switcher {
    margin-left: 4px;
  }

  .header-context {
    display: none;
  }
}

/* ── Welcome (not connected — Inspect mode) ── */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
}

.welcome-icon {
  font-size: 48px;
  color: var(--accent);
  margin-bottom: 1rem;
  opacity: 0.6;
}

.welcome-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.welcome-text {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 420px;
  line-height: 1.6;
  margin: 0 0 1.5rem;
}

.welcome-connect {
  display: flex;
  gap: 8px;
  width: 100%;
  max-width: 480px;
  margin-bottom: 1rem;
}

.welcome-input {
  flex: 1;
  height: 42px;
  padding: 0 16px;
  background: var(--bg-input);
  border: 2px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.welcome-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.6;
}

.welcome-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.welcome-btn {
  height: 42px;
  padding: 0 24px;
  font-size: 14px;
  border-radius: var(--radius);
}

.welcome-error {
  color: var(--error);
  font-size: 13px;
  margin: 0 0 1rem;
}

.welcome-examples {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 0.5rem;
}

.welcome-examples-label {
  font-size: 12px;
  color: var(--text-muted);
}

.example-link {
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--accent);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: all var(--transition);
}

.example-link:hover {
  background: var(--accent-glow);
  border-color: var(--accent);
}
</style>
