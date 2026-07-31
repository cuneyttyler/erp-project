import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient } from '@/shared/api/client'
import { useTenantStore, type PackageKey } from '@/shared/stores/tenant'

export interface Role {
  id: number
  name: string
  granted_actions: Record<string, string[]>
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
  roles: Role[]
  tenant: TenantInfo
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const isAuthenticated = computed(() => user.value !== null)
  // Distinguishes "we haven't checked yet" from "checked, no session" so the
  // router guard doesn't flash the login page before the initial /me/ call
  // resolves (technical.md §10.1's guard pattern, applied to auth instead of
  // package-gating).
  const isInitialized = ref(false)

  function applyUser(data: CurrentUser | null) {
    user.value = data
    const tenantStore = useTenantStore()
    if (data?.tenant) {
      tenantStore.setActivePackages(data.tenant.active_packages)
      if (data.tenant.subscription_tier) tenantStore.subscriptionTier = data.tenant.subscription_tier
    } else {
      tenantStore.setActivePackages([])
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

  return { user, isAuthenticated, isInitialized, login, logout, fetchMe, fetchCsrfCookie }
})
