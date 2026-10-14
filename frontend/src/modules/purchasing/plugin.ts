import { ShoppingCartIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const purchasingPlugin: PluginManifest = {
  key: 'purchasing',
  package: 'purchasing',
  icon: ShoppingCartIcon,
  navGroup: 'inventory',
  pages: [
    { path: '/purchase-orders', action: 'purchase_order.view', name: 'purchase-orders', labelKey: 'nav.purchaseOrders', icon: ShoppingCartIcon, component: () => import('./views/PurchaseOrdersView.vue') },
  ],
}
