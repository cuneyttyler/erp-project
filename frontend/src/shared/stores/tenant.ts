import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

// The tenant's active_packages list (technical.md §5 `Tenant` entity) drives
// which package modules the router/nav actually load (technical.md §10.1) --
// a tenant without the Manufacturing package never downloads that bundle.
export const AVAILABLE_PACKAGES = [
  'purchasing',
  'inventory',
  'manufacturing',
  'sales_crm',
  'hr_payroll',
  'projects',
  'pos',
  'ecommerce',
  'bi_analytics',
] as const

export type PackageKey = (typeof AVAILABLE_PACKAGES)[number]

export const useTenantStore = defineStore('tenant', () => {
  const activePackages = ref<PackageKey[]>([])
  const subscriptionTier = ref<'starter' | 'growth' | 'professional' | 'enterprise'>('starter')

  const hasPackage = computed(() => (pkg: PackageKey) => activePackages.value.includes(pkg))

  function setActivePackages(packages: PackageKey[]) {
    activePackages.value = packages
  }

  return { activePackages, subscriptionTier, hasPackage, setActivePackages }
})
