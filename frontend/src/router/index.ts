import { createRouter, createWebHistory } from 'vue-router'

import ChartOfAccountsView from '@/core/views/ChartOfAccountsView.vue'
import DashboardView from '@/core/views/DashboardView.vue'
import JournalEntriesView from '@/core/views/JournalEntriesView.vue'
import LoginView from '@/core/views/LoginView.vue'
import TrialBalanceView from '@/core/views/TrialBalanceView.vue'
import { useAuthStore } from '@/shared/stores/auth'

// technical.md §10.1: package routes are added here as each module lands, and
// are only registered/downloaded for tenants whose active_packages include
// them -- e.g.:
//
//   {
//     path: '/purchasing',
//     component: () => import('@/modules/purchasing/PurchasingHome.vue'),
//     meta: { requiresPackage: 'purchasing' },
//   }
//
// The Core (non-package) routes below are always available -- Core ships
// with every subscription tier (product.md §6.1).
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/accounts', name: 'accounts', component: ChartOfAccountsView },
    { path: '/journal-entries', name: 'journal-entries', component: JournalEntriesView },
    { path: '/trial-balance', name: 'trial-balance', component: TrialBalanceView },
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
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
  return true
})
