import { ClipboardDocumentListIcon, GlobeAltIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const ecommercePlugin: PluginManifest = {
  key: 'ecommerce',
  package: 'ecommerce',
  icon: GlobeAltIcon,
  navGroup: 'ecommerce',
  pages: [
    { path: '/ecommerce/accounts', action: 'marketplace_account.view', name: 'ecommerce-accounts', labelKey: 'nav.ecommerceAccounts', icon: GlobeAltIcon, component: () => import('./views/MarketplaceAccountsView.vue') },
    { path: '/ecommerce/orders', action: 'marketplace_order.view', name: 'ecommerce-orders', labelKey: 'nav.ecommerceOrders', icon: ClipboardDocumentListIcon, component: () => import('./views/MarketplaceOrdersView.vue') },
  ],
}
