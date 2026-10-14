import { ArchiveBoxIcon, ChartBarIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const inventoryPlugin: PluginManifest = {
  key: 'inventory',
  package: 'inventory',
  icon: ArchiveBoxIcon,
  navGroup: 'inventory',
  pages: [
    { path: '/warehouses', action: 'warehouse.view', name: 'warehouses', labelKey: 'nav.warehouses', icon: ArchiveBoxIcon, component: () => import('./views/WarehousesView.vue') },
    { path: '/stock-levels', action: 'stock_level.view', name: 'stock-levels', labelKey: 'nav.stockLevels', icon: ChartBarIcon, component: () => import('./views/StockLevelsView.vue') },
  ],
}
