import type { RouteRecordRaw } from 'vue-router'

import { corePlugins } from '@/core/plugins'
import { biPlugin } from '@/modules/bi/plugin'
import { ecommercePlugin } from '@/modules/ecommerce/plugin'
import { hrPayrollPlugin } from '@/modules/hr_payroll/plugin'
import { inventoryPlugin } from '@/modules/inventory/plugin'
import { manufacturingPlugin } from '@/modules/manufacturing/plugin'
import { posPlugin } from '@/modules/pos/plugin'
import { purchasingPlugin } from '@/modules/purchasing/plugin'
import { salesCrmPlugin } from '@/modules/sales_crm/plugin'

import type { NavGroupId, PluginManifest } from './types'

// Every plugin the app knows about. The router's routes and the sidebar's
// links are both generated from this list -- adding a page to the app means
// adding it to a plugin's manifest, never to the router or sidebar directly.
// Order matters: it's the order plugins (and their pages) appear within a
// nav group and on the plugin-management page.
export const plugins: PluginManifest[] = [
  ...corePlugins,
  inventoryPlugin,
  purchasingPlugin,
  salesCrmPlugin,
  manufacturingPlugin,
  hrPayrollPlugin,
  posPlugin,
  ecommercePlugin,
  biPlugin,
]

export const pluginsByKey: Record<string, PluginManifest> = Object.fromEntries(plugins.map((p) => [p.key, p]))

// REQ-CORE-UX-005: related screens live under a collapsible section rather
// than one flat list that grows with every plugin a tenant installs.
export const navGroups: { id: NavGroupId; labelKey: string }[] = [
  { id: 'finance', labelKey: 'nav.groups.finance' },
  { id: 'inventory', labelKey: 'nav.groups.inventory' },
  { id: 'sales', labelKey: 'nav.groups.sales' },
  { id: 'manufacturing', labelKey: 'nav.groups.manufacturing' },
  { id: 'hr', labelKey: 'nav.groups.hr' },
  { id: 'pos', labelKey: 'nav.groups.pos' },
  { id: 'ecommerce', labelKey: 'nav.groups.ecommerce' },
  { id: 'bi', labelKey: 'nav.groups.bi' },
]

// `meta.plugin` and `meta.action` are what the router guard checks: a route
// is only reachable while its plugin is active for the tenant and the user
// holds the page's action.
export const pluginRoutes: RouteRecordRaw[] = plugins.flatMap((plugin) =>
  plugin.pages.map((page) => ({
    path: page.path,
    name: page.name,
    component: page.component,
    meta: { plugin: plugin.key, action: page.action },
  })),
)
