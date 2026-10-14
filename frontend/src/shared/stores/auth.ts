import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { useAIStore } from '@/ai-panel/store'
import { apiClient } from '@/shared/api/client'
import { usePluginStore } from '@/shared/stores/plugins'
import { useTenantStore, type PackageKey } from '@/shared/stores/tenant'

// What the signed-in user may do (backend apps/access). `actions` are
// catalog codes like `invoice.create` -- already narrowed to plugins that
// are installed, so one check answers both "is it there" and "may I".
export interface AccessInfo {
  is_org_admin: boolean
  actions: string[]
}

export interface TenantInfo {
  active_packages: PackageKey[]
  subscription_tier: 'starter' | 'growth' | 'professional' | 'enterprise' | null
}

export interface CurrentUser {
  id: number
  username: string
  email: string
  full_name: string
  preferred_locale: 'tr' | 'en'
  mfa_enabled: boolean
  tenant: TenantInfo
  access: AccessInfo
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const isAuthenticated = computed(() => user.value !== null)
  // Distinguishes "we haven't checked yet" from "checked, no session" so the
  // router guard doesn't flash the login page before the initial /me/ call
  // resolves (technical.md §10.1's guard pattern, applied to auth instead of
  // package-gating).
  const isInitialized = ref(false)

  const isOrgAdmin = computed(() => user.value?.access?.is_org_admin ?? false)
  const actionSet = computed(() => new Set(user.value?.access?.actions ?? []))
  // Only ever used to decide what to *offer* -- the API enforces the same
  // rule on every request regardless of what the UI shows.
  const can = computed(() => (action: string) => actionSet.value.has(action))

  function applyUser(data: CurrentUser | null) {
    user.value = data
    const tenantStore = useTenantStore()
    if (data?.tenant) {
      tenantStore.setActivePackages(data.tenant.active_packages)
      if (data.tenant.subscription_tier) tenantStore.subscriptionTier = data.tenant.subscription_tier
    } else {
      tenantStore.setActivePackages([])
      // Plugin/panel state and assistant conversations belong to the session
      // that loaded them -- the next user to log in on this tab must get
      // their own, not this one's.
      usePluginStore().reset()
      useAIStore().reset()
    }
  }

  // Auth lives in apps/core, mounted at /api/v1/core/ (config/urls.py) --
  // the "core/" prefix here mirrors how a future purchasing store would call
  // "purchasing/..." against its own app's mount point (technical.md §6).
  async function fetchCsrfCookie() {
    await apiClient.get('core/auth/csrf/')
  }

  async function login(username: string, password: string) {
    await fetchCsrfCookie()
    const { data } = await apiClient.post<CurrentUser>('core/auth/login/', { username, password })
    applyUser(data)
  }

  async function logout() {
    await apiClient.post('core/auth/logout/')
    applyUser(null)
  }

  async function fetchMe() {
    try {
      const { data } = await apiClient.get<CurrentUser>('core/auth/me/')
      applyUser(data)
    } catch {
      applyUser(null)
    } finally {
      isInitialized.value = true
    }
  }

  return { user, isAuthenticated, isInitialized, isOrgAdmin, can, login, logout, fetchMe, fetchCsrfCookie }
})
