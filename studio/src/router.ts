import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import { checkApiAvailability } from './design/store'
import { projectStore } from './design/project-store'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

const inspectOnly = !!import.meta.env.VITE_INSPECT_ONLY
const desktopMode = !!import.meta.env.VITE_STUDIO_DESKTOP

// Only include Design routes in standalone builds (not embedded runtime packages)
const designRoutes = inspectOnly ? [] : [
  // ── Project routes (primary) ──
  {
    path: '/design',
    name: 'workspace-list',
    component: () => import('./views/WorkspaceListView.vue'),
  },
  {
    path: '/design/workspaces/:workspaceId',
    name: 'project-list',
    component: () => import('./views/ProjectListView.vue'),
  },
  {
    path: '/design/projects/:projectId',
    redirect: (to: any) => `/design/projects/${to.params.projectId}/pm`,
  },
  {
    path: '/design/projects/:projectId/dashboard',
    name: 'project-dashboard',
    component: () => import('./views/ProjectDashboardView.vue'),
  },
  {
    path: '/design/projects/:projectId/fronting',
    name: 'project-fronting-express',
    component: () => import('./views/FrontingExpressView.vue'),
  },
  {
    path: '/design/projects/:projectId/templates/export',
    name: 'project-template-export',
    component: () => import('./views/ProjectTemplateExportView.vue'),
  },
  {
    path: '/design/projects/:projectId/source-docs',
    name: 'project-source-docs',
    component: () => import('./views/SourceDocsView.vue'),
  },
  {
    path: '/design/projects/:projectId/assistant',
    name: 'project-ai-assistant',
    component: () => import('./views/ProjectAssistantView.vue'),
  },
  {
    path: '/design/projects/:projectId/pm/assistant',
    name: 'project-product-ai-assistant',
    component: () => import('./views/ProjectAssistantView.vue'),
    meta: { assistantLane: 'pm' },
  },
  {
    path: '/design/projects/:projectId/developer/assistant',
    name: 'project-developer-ai-assistant',
    component: () => import('./views/ProjectAssistantView.vue'),
    meta: { assistantLane: 'dev' },
  },
  {
    path: '/design/projects/:projectId/verification',
    name: 'project-verification',
    component: () => import('./views/ProjectVerificationView.vue'),
  },
  {
    path: '/design/projects/:projectId/revisions',
    name: 'project-revisions',
    component: () => import('./views/RevisionHistoryView.vue'),
  },
  {
    path: '/design/projects/:projectId/pm',
    name: 'project-pm',
    component: () => import('./views/ProjectPmHomeView.vue'),
  },
  {
    path: '/design/projects/:projectId/pm/diagrams',
    name: 'project-product-diagrams',
    component: () => import('./views/ProductDiagramsView.vue'),
  },
  {
    path: '/design/projects/:projectId/product-summary',
    name: 'project-product-summary',
    component: () => import('./views/ProductSummaryView.vue'),
  },
  {
    path: '/design/projects/:projectId/actor-model',
    name: 'project-actor-model',
    component: () => import('./views/ActorModelView.vue'),
  },
  {
    path: '/design/projects/:projectId/business-areas',
    name: 'project-business-areas',
    component: () => import('./views/BusinessAreasView.vue'),
  },
  {
    path: '/design/projects/:projectId/permission-intent',
    name: 'project-permission-intent',
    component: () => import('./views/PermissionIntentView.vue'),
  },
  {
    path: '/design/projects/:projectId/requirements',
    name: 'project-requirements-list',
    component: () => import('./views/RequirementsListView.vue'),
  },
  {
    path: '/design/projects/:projectId/scenarios',
    name: 'project-scenarios-list',
    component: () => import('./views/ScenariosListView.vue'),
  },
  {
    path: '/design/projects/:projectId/pm-artifacts',
    name: 'project-pm-artifacts',
    component: () => import('./views/PmArtifactsView.vue'),
  },
  {
    path: '/design/projects/:projectId/pm-review',
    name: 'project-pm-review',
    component: () => import('./views/PmReviewView.vue'),
  },
  {
    path: '/design/projects/:projectId/shapes',
    name: 'project-shapes',
    component: () => import('./views/ProjectShapesView.vue'),
  },
  {
    path: '/design/projects/:projectId/non-goals',
    name: 'project-non-goals',
    component: () => import('./views/NonGoalsView.vue'),
  },
  {
    path: '/design/projects/:projectId/success-criteria',
    name: 'project-success-criteria',
    component: () => import('./views/SuccessCriteriaView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer',
    name: 'project-developer-home',
    component: () => import('./views/DeveloperDesignHomeView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/diagrams',
    name: 'project-developer-diagrams',
    component: () => import('./views/DeveloperDiagramsView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/handoff',
    name: 'project-developer-handoff',
    component: () => import('./views/DeveloperHandoffView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/source-docs',
    name: 'project-developer-source-docs',
    component: () => import('./views/SourceDocsView.vue'),
    meta: { sourceDocsLane: 'dev' },
  },
  {
    path: '/design/projects/:projectId/developer/service-formalization',
    name: 'project-developer-service-formalization',
    component: () => import('./views/DeveloperServiceFormalizationView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/governance-bindings',
    name: 'project-developer-governance-bindings',
    component: () => import('./views/DeveloperGovernanceBindingsView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/audit-lineage',
    name: 'project-developer-audit-lineage',
    component: () => import('./views/DeveloperAuditLineageView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/capability-formalization',
    name: 'project-developer-capability-formalization',
    component: () => import('./views/DeveloperCapabilityFormalizationView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/data-contract-formalization',
    name: 'project-developer-data-contract-formalization',
    component: () => import('./views/DeveloperDataContractFormalizationView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/scenario-formalization',
    name: 'project-developer-scenario-formalization',
    component: () => import('./views/DeveloperScenarioFormalizationView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/scenario-execution-semantics',
    name: 'project-developer-scenario-execution-semantics',
    component: () => import('./views/DeveloperScenarioExecutionSemanticsView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/generation-settings',
    name: 'project-developer-generation-settings',
    component: () => import('./views/DeveloperGenerationSettingsView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/verification-expectations',
    name: 'project-developer-verification-expectations',
    component: () => import('./views/DeveloperVerificationExpectationsView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/definition',
    name: 'project-developer-definition',
    component: () => import('./views/DeveloperDefinitionView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/coverage',
    name: 'project-developer-coverage',
    component: () => import('./views/DeveloperCoverageView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/app-glue',
    name: 'project-developer-app-glue',
    component: () => import('./views/DeveloperCoverageView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/app-customization',
    name: 'project-developer-app-customization',
    component: () => import('./views/DeveloperAppCustomizationView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/data-access/:section?',
    name: 'project-data-access-design',
    component: () => import('./views/DataAccessDesignView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/application-integration/:section?',
    name: 'project-application-integration-design',
    component: () => import('./views/ApplicationIntegrationDesignView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/integration-fronting',
    name: 'project-integration-fronting',
    component: () => import('./views/IntegrationFrontingView.vue'),
  },
  {
    path: '/design/projects/:projectId/developer/gaps',
    name: 'project-developer-gaps',
    component: () => import('./views/DeveloperGapsView.vue'),
  },
  {
    path: '/design/projects/:projectId/overview',
    redirect: (to: any) => `/design/projects/${to.params.projectId}/pm`,
  },
  {
    path: '/design/projects/:projectId/first-draft',
    name: 'first-draft-review',
    component: () => import('./views/FirstDraftReviewView.vue'),
  },
  {
    path: '/design/projects/:projectId/requirements/:id',
    name: 'requirements',
    component: () => import('./views/RequirementsView.vue'),
  },
  {
    path: '/design/projects/:projectId/scenarios/:id',
    name: 'scenario-detail',
    component: () => import('./views/ScenarioDetailView.vue'),
  },
  {
    path: '/design/projects/:projectId/proposals/:id',
    name: 'proposal',
    component: () => import('./views/ProposalView.vue'),
  },
  {
    path: '/design/projects/:projectId/shapes/:id',
    name: 'shape',
    component: () => import('./views/ShapeView.vue'),
  },
  {
    path: '/design/projects/:projectId/evaluations/:id',
    name: 'evaluation',
    component: () => import('./views/EvaluationView.vue'),
  },
  {
    path: '/developer',
    redirect: () => {
      const pid = projectStore.activeProject?.id
      return pid ? `/design/projects/${pid}/developer` : '/design'
    },
  },
  {
    path: '/developer/data-access',
    redirect: () => {
      const pid = projectStore.activeProject?.id
      return pid ? `/design/projects/${pid}/developer/data-access` : '/design'
    },
  },
  {
    path: '/developer/application-integration',
    redirect: () => {
      const pid = projectStore.activeProject?.id
      return pid ? `/design/projects/${pid}/developer/application-integration` : '/design'
    },
  },
  {
    path: '/data-access',
    redirect: '/developer/data-access',
  },
  {
    path: '/application-integration',
    redirect: '/developer/application-integration',
  },
]

const routes = [
  // Studio home
  {
    path: '/',
    name: 'studio-home',
    component: () => import('./views/StudioHomeView.vue'),
  },

  // ── Inspect mode ──
  {
    path: '/inspect',
    redirect: '/inspect/discovery',
  },
  {
    path: '/inspect/discovery',
    name: 'discovery',
    component: () => import('./views/DiscoveryView.vue'),
  },
  {
    path: '/inspect/manifest',
    name: 'manifest',
    component: () => import('./views/ManifestView.vue'),
  },
  {
    path: '/inspect/jwks',
    name: 'jwks',
    component: () => import('./views/JwksView.vue'),
  },
  {
    path: '/inspect/audit',
    name: 'audit',
    component: () => import('./views/AuditView.vue'),
  },
  {
    path: '/inspect/approvals',
    name: 'approvals',
    component: () => import('./views/ApprovalReviewView.vue'),
  },
  {
    path: '/inspect/checkpoints',
    name: 'checkpoints',
    component: () => import('./views/CheckpointsView.vue'),
  },
  {
    path: '/inspect/invoke/:capability?',
    name: 'invoke',
    component: () => import('./views/InvokeView.vue'),
  },

  // ── Design mode (excluded from Inspect-only builds) ──
  ...designRoutes,

  // ── Backward-compat redirects (old flat paths → /inspect/*) ──
  { path: '/manifest', redirect: '/inspect/manifest' },
  { path: '/jwks', redirect: '/inspect/jwks' },
  { path: '/audit', redirect: '/inspect/audit' },
  { path: '/approvals', redirect: '/inspect/approvals' },
  { path: '/checkpoints', redirect: '/inspect/checkpoints' },
  { path: '/invoke/:capability?', redirect: (to: any) => `/inspect/invoke/${to.params.capability || ''}` },
]

export const router = createRouter({
  history: desktopMode
    ? createWebHashHistory()
    : createWebHistory(normalizeBase(import.meta.env.VITE_BASE_PATH || '/studio/')),
  routes,
})

// Check API availability when entering Design mode routes
router.beforeEach((to, _from, next) => {
  if (typeof to.path === 'string' && (to.path.startsWith('/design') || to.path.startsWith('/developer'))) {
    checkApiAvailability()
  }
  next()
})
