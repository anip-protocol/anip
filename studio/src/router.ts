import { createRouter, createWebHistory } from 'vue-router'
import { checkApiAvailability } from './design/store'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

const inspectOnly = !!import.meta.env.VITE_INSPECT_ONLY

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
    name: 'project-overview',
    component: () => import('./views/ProjectOverviewView.vue'),
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
  // ── Legacy pack routes (read-only fallback) ──
  {
    path: '/design/packs/:packId',
    name: 'pack-detail',
    component: () => import('./views/ScenarioDetailView.vue'),
  },
  {
    path: '/design/packs/:packId/requirements',
    name: 'pack-requirements',
    component: () => import('./views/RequirementsView.vue'),
  },
  {
    path: '/design/packs/:packId/proposal',
    name: 'pack-proposal',
    component: () => import('./views/ProposalView.vue'),
  },
  {
    path: '/design/packs/:packId/evaluation',
    name: 'pack-evaluation',
    component: () => import('./views/EvaluationView.vue'),
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
  { path: '/checkpoints', redirect: '/inspect/checkpoints' },
  { path: '/invoke/:capability?', redirect: (to: any) => `/inspect/invoke/${to.params.capability || ''}` },
]

export const router = createRouter({
  history: createWebHistory(normalizeBase(import.meta.env.VITE_BASE_PATH || '/studio/')),
  routes,
})

// Check API availability when entering Design mode routes
router.beforeEach((to, _from, next) => {
  if (typeof to.path === 'string' && to.path.startsWith('/design')) {
    checkApiAvailability()
  }
  next()
})
