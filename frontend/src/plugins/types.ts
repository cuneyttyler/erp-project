import type { Component } from 'vue'

import type { PackageKey } from '@/shared/stores/tenant'

// A plugin is a unit of UI surface a tenant can add to or remove from the
// app: the left-nav pages listed here, plus the home-panel widgets the
// backend registers under the same key (backend/apps/plugins/registry.py is
// the matching catalog -- `key` and `package` must agree with it).
export interface PluginPage {
  path: string
  name: string
  labelKey: string
  icon: Component
  // The catalog action a user needs to be offered this page -- the "view"
  // action of the resource the page is mainly about.
  action: string
  // Always a dynamic import, so a plugin's screens are only downloaded by
  // tenants that have it installed (technical.md §10.1).
  component: () => Promise<unknown>
}

export type NavGroupId = 'finance' | 'inventory' | 'sales' | 'manufacturing' | 'hr' | 'pos' | 'ecommerce' | 'bi'

export interface PluginManifest {
  key: string
  // The subscription package that licenses it; omitted = ships with Core.
  package?: PackageKey
  icon: Component
  navGroup: NavGroupId
  pages: PluginPage[]
}
