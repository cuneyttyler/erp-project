import { ClockIcon, Cog6ToothIcon, ComputerDesktopIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const posPlugin: PluginManifest = {
  key: 'pos',
  package: 'pos',
  icon: ComputerDesktopIcon,
  navGroup: 'pos',
  pages: [
    { path: '/pos', action: 'pos_shift.view', name: 'pos-checkout', labelKey: 'nav.posCheckout', icon: ComputerDesktopIcon, component: () => import('./views/POSCheckoutView.vue') },
    { path: '/pos/shifts', action: 'pos_shift.view', name: 'pos-shifts', labelKey: 'nav.posShifts', icon: ClockIcon, component: () => import('./views/POSShiftsView.vue') },
    { path: '/pos/setup', action: 'pos_store.view', name: 'pos-setup', labelKey: 'nav.posSetup', icon: Cog6ToothIcon, component: () => import('./views/POSSetupView.vue') },
  ],
}
