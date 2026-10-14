import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from '@/core/views/DashboardView.vue'
import LoginView from '@/core/views/LoginView.vue'
import { pluginRoutes } from '@/plugins/registry'
import { useAuthStore } from '@/shared/stores/auth'
import { usePluginStore } from '@/shared/stores/plugins'

// The routes declared here are the system screens -- the public homepage,
// login, the home panel, the AI assistant, the audit log, and the two administration pages
// (plugins, users & roles). None of them can be removed. Every other page
// belongs to a plugin and is generated from its manifest
// (src/plugins/registry.ts), carrying `meta.plugin` and `meta.action`. A
// user can still type the URL of a page they aren't offered (Vue Router
// doesn't "not know" a route the way a server-rendered app would), but the
// guard below stops them reaching the view, the sidebar doesn't link to it,
// its lazy chunk is never downloaded (technical.md §10.1) -- and the API
// behind it refuses them regardless.
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // The public homepage. A signed-in visitor is sent on to their panel.
    { path: '/', name: 'home', component: () => import('@/landing/LandingView.vue'), meta: { public: true, bare: true } },
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/panel', name: 'dashboard', component: DashboardView },
    { path: '/assistant', name: 'assistant', component: () => import('@/ai-panel/AssistantView.vue') },
    { path: '/audit-log', name: 'audit-log', component: () => import('@/core/views/AuditLogView.vue') },
    { path: '/plugins', name: 'plugins', component: () => import('@/core/views/PluginsView.vue') },
    { path: '/users', name: 'users', component: () => import('@/core/views/UsersView.vue'), meta: { orgAdmin: true } },
    ...pluginRoutes,
    { path: '/:pathMatch(.*)*', redirect: { name: 'dashboard' } },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.isInitialized) {
    await auth.fetchMe()
  }
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if ((to.name === 'login' || to.name === 'home') && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
  if (auth.isAuthenticated) {
    const plugins = usePluginStore()
    if (!plugins.isLoaded) {
      // A failed load isn't fatal: isActive() falls back to the tenant's
      // subscription, and the next navigation retries.
      await plugins.load().catch(() => undefined)
    }
    const requiredPlugin = to.meta.plugin as string | undefined
    if (requiredPlugin && !plugins.isActive(requiredPlugin)) {
      return { name: 'dashboard' }
    }
    const requiredAction = to.meta.action as string | undefined
    if (requiredAction && !auth.can(requiredAction)) {
      return { name: 'dashboard' }
    }
    if (to.meta.orgAdmin && !auth.isOrgAdmin) {
      return { name: 'dashboard' }
    }
  }
  return true
})
