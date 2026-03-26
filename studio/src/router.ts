import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'discovery',
    component: () => import('./views/DiscoveryView.vue'),
  },
  {
    path: '/manifest',
    name: 'manifest',
    component: () => import('./views/ManifestView.vue'),
  },
  {
    path: '/jwks',
    name: 'jwks',
    component: () => import('./views/JwksView.vue'),
  },
  {
    path: '/audit',
    name: 'audit',
    component: () => import('./views/AuditView.vue'),
  },
  {
    path: '/checkpoints',
    name: 'checkpoints',
    component: () => import('./views/CheckpointsView.vue'),
  },
  {
    path: '/invoke/:capability?',
    name: 'invoke',
    component: () => import('./views/InvokeView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory('/studio/'),
  routes,
})
