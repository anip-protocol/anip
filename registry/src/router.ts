import { createRouter, createWebHistory } from 'vue-router'
import PublicationListView from './views/PublicationListView.vue'
import PackageDetailView from './views/PackageDetailView.vue'
import TemplateDetailView from './views/TemplateDetailView.vue'
import TemplateListView from './views/TemplateListView.vue'
import PublisherSelfServiceView from './views/PublisherSelfServiceView.vue'
import AdminModerationView from './views/AdminModerationView.vue'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : `${base}/`
}

export const router = createRouter({
  history: createWebHistory(normalizeBase(import.meta.env.BASE_URL || '/')),
  routes: [
    {
      path: '/',
      redirect: '/packages',
    },
    {
      path: '/packages',
      name: 'publications',
      component: PublicationListView,
    },
    {
      path: '/templates',
      name: 'templates',
      component: TemplateListView,
    },
    {
      path: '/publisher',
      name: 'publisher-self-service',
      component: PublisherSelfServiceView,
    },
    {
      path: '/admin',
      name: 'admin-moderation',
      component: AdminModerationView,
    },
    {
      path: '/templates/:templateId/:version',
      name: 'template-detail',
      component: TemplateDetailView,
      props: true,
    },
    {
      path: '/packages/:packageId/:version',
      name: 'package-detail',
      component: PackageDetailView,
      props: true,
    },
  ],
})
