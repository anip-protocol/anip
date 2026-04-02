import { createRouter, createWebHistory } from 'vue-router'
import { checkApiAvailability } from './design/store'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

const inspectOnly = !!import.meta.env.VITE_INSPECT_ONLY

// Only include Design routes in standalone builds (not embedded runtime packages)
const designRoutes = inspectOnly ? [] : [
  {
    path: '/design',
    name: 'design-home',
    component: () => import('./views/DesignHomeView.vue'),
  },
  {
    path: '/design/scenarios',
    name: 'scenario-browser',
    component: () => import('./views/ScenarioBrowserView.vue'),
  },
  {
    path: '/design/scenarios/:pack',
    name: 'scenario-detail',
    component: () => import('./views/ScenarioDetailView.vue'),
  },
  {
    path: '/design/requirements/:pack',
    name: 'requirements',
    component: () => import('./views/RequirementsView.vue'),
  },
  {
    path: '/design/proposal/:pack',
    name: 'proposal',
    component: () => import('./views/ProposalView.vue'),
  },
  {
    path: '/design/evaluation/:pack',
    name: 'evaluation',
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
