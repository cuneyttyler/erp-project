import { TruckIcon, UserPlusIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const salesCrmPlugin: PluginManifest = {
  key: 'sales_crm',
  package: 'sales_crm',
  icon: UserPlusIcon,
  navGroup: 'sales',
  pages: [
    { path: '/leads', action: 'lead.view', name: 'leads', labelKey: 'nav.leads', icon: UserPlusIcon, component: () => import('./views/LeadsView.vue') },
    { path: '/sales-orders', action: 'sales_order.view', name: 'sales-orders', labelKey: 'nav.salesOrders', icon: TruckIcon, component: () => import('./views/SalesOrdersView.vue') },
  ],
}
