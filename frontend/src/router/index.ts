import { createRouter, createWebHistory } from 'vue-router'

import AgingView from '@/core/views/AgingView.vue'
import BillsView from '@/core/views/BillsView.vue'
import ChartOfAccountsView from '@/core/views/ChartOfAccountsView.vue'
import DashboardView from '@/core/views/DashboardView.vue'
import InvoicesView from '@/core/views/InvoicesView.vue'
import ItemsView from '@/core/views/ItemsView.vue'
import JournalEntriesView from '@/core/views/JournalEntriesView.vue'
import LoginView from '@/core/views/LoginView.vue'
import PartiesView from '@/core/views/PartiesView.vue'
import TrialBalanceView from '@/core/views/TrialBalanceView.vue'
import StockLevelsView from '@/modules/inventory/views/StockLevelsView.vue'
import WarehousesView from '@/modules/inventory/views/WarehousesView.vue'
import PurchaseOrdersView from '@/modules/purchasing/views/PurchaseOrdersView.vue'
import LeadsView from '@/modules/sales_crm/views/LeadsView.vue'
import SalesOrdersView from '@/modules/sales_crm/views/SalesOrdersView.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useTenantStore } from '@/shared/stores/tenant'

// technical.md §10.1: package routes carry `meta.requiresPackage` and are
// rejected by the guard below unless the tenant's active_packages includes
// that key -- a tenant without Purchasing/Inventory can still navigate to
// these paths (Vue Router doesn't "not download" a route the way a
// server-rendered app would), but the guard stops them from actually
// reaching the view, and the nav (App.vue) doesn't link to it in the first
// place. The Core (non-package) routes ship with every subscription tier
// (product.md §6.1) and carry no such gate.
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/accounts', name: 'accounts', component: ChartOfAccountsView },
    { path: '/items', name: 'items', component: ItemsView },
    { path: '/journal-entries', name: 'journal-entries', component: JournalEntriesView },
    { path: '/trial-balance', name: 'trial-balance', component: TrialBalanceView },
    { path: '/parties', name: 'parties', component: PartiesView },
    { path: '/invoices', name: 'invoices', component: InvoicesView },
    { path: '/bills', name: 'bills', component: BillsView },
    { path: '/aging', name: 'aging', component: AgingView },
    {
      path: '/warehouses',
      name: 'warehouses',
      component: WarehousesView,
      meta: { requiresPackage: 'inventory' },
    },
    {
      path: '/stock-levels',
      name: 'stock-levels',
      component: StockLevelsView,
      meta: { requiresPackage: 'inventory' },
    },
    {
      path: '/purchase-orders',
      name: 'purchase-orders',
      component: PurchaseOrdersView,
      meta: { requiresPackage: 'purchasing' },
    },
    {
      path: '/leads',
      name: 'leads',
      component: LeadsView,
      meta: { requiresPackage: 'sales_crm' },
    },
    {
      path: '/sales-orders',
      name: 'sales-orders',
      component: SalesOrdersView,
      meta: { requiresPackage: 'sales_crm' },
    },
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
  const requiredPackage = to.meta.requiresPackage as string | undefined
  if (requiredPackage) {
    const tenant = useTenantStore()
    if (!tenant.hasPackage(requiredPackage as any)) {
      return { name: 'dashboard' }
    }
  }
  return true
})
