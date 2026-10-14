import { ClipboardDocumentListIcon, CogIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const manufacturingPlugin: PluginManifest = {
  key: 'manufacturing',
  package: 'manufacturing',
  icon: CogIcon,
  navGroup: 'manufacturing',
  pages: [
    { path: '/boms', action: 'bom.view', name: 'boms', labelKey: 'nav.boms', icon: ClipboardDocumentListIcon, component: () => import('./views/BOMsView.vue') },
    { path: '/work-orders', action: 'work_order.view', name: 'work-orders', labelKey: 'nav.workOrders', icon: CogIcon, component: () => import('./views/WorkOrdersView.vue') },
  ],
}
