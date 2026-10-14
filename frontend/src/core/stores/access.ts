import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient } from '@/shared/api/client'

// Users, roles, permissions and the action catalog they're built from
// (backend apps/access). The chain is: an action goes into a permission, a
// permission into a role, a role onto a user -- plus individual actions
// granted to a user directly.

export interface CatalogOperation {
  name: string
  // The catalog code, `<resource>.<operation>`.
  code: string
  kind: 'read' | 'write'
}

export interface CatalogResource {
  key: string
  description: string
  operations: CatalogOperation[]
}

export interface CatalogGroup {
  // A plugin key.
  group: string
  resources: CatalogResource[]
}

export interface Permission {
  id: number
  name: string
  description: string
  actions: string[]
  // Set on the built-in permissions, which are read-only.
  system_key: string | null
  is_system: boolean
  role_count: number
}

export interface Role {
  id: number
  name: string
  description: string
  permission_ids: number[]
  // The organization-admin role: holds every action.
  grants_all: boolean
  system_key: string | null
  is_system: boolean
  user_count: number
}

export interface ManagedUser {
  id: number
  username: string
  first_name: string
  last_name: string
  full_name: string
  email: string
  is_active: boolean
  preferred_locale: 'tr' | 'en'
  role_ids: number[]
  direct_actions: string[]
  is_org_admin: boolean
  last_login: string | null
}

export type UserPayload = Partial<Pick<ManagedUser, 'username' | 'first_name' | 'last_name' | 'email' | 'is_active' | 'preferred_locale' | 'role_ids' | 'direct_actions'>> & {
  password?: string
}

export const useAccessStore = defineStore('access', () => {
  const catalog = ref<CatalogGroup[]>([])
  const permissions = ref<Permission[]>([])
  const roles = ref<Role[]>([])
  const users = ref<ManagedUser[]>([])

  const actionCount = computed(() => catalog.value.reduce((sum, g) => sum + g.resources.reduce((n, r) => n + r.operations.length, 0), 0))

  async function fetchCatalog() {
    const { data } = await apiClient.get<CatalogGroup[]>('access/actions/')
    catalog.value = data
  }

  async function fetchAll() {
    // Roles first: listing them is what makes the backend create the
    // built-in roles and permissions on a tenant that has none yet.
    const roleResponse = await apiClient.get<Role[]>('access/roles/')
    roles.value = roleResponse.data
    const [permissionResponse, userResponse] = await Promise.all([
      apiClient.get<Permission[]>('access/permissions/'),
      apiClient.get<ManagedUser[]>('access/users/'),
      fetchCatalog(),
    ])
    permissions.value = permissionResponse.data
    users.value = userResponse.data
  }

  function upsert<T extends { id: number }>(list: T[], item: T) {
    const index = list.findIndex((existing) => existing.id === item.id)
    if (index === -1) list.push(item)
    else list[index] = item
  }

  async function savePermission(payload: { name: string; description: string; actions: string[] }, id?: number) {
    const { data } = id
      ? await apiClient.patch<Permission>(`access/permissions/${id}/`, payload)
      : await apiClient.post<Permission>('access/permissions/', payload)
    upsert(permissions.value, data)
    return data
  }

  async function deletePermission(id: number) {
    await apiClient.delete(`access/permissions/${id}/`)
    permissions.value = permissions.value.filter((p) => p.id !== id)
    // Roles that held it no longer do.
    roles.value = roles.value.map((role) => ({ ...role, permission_ids: role.permission_ids.filter((pid) => pid !== id) }))
  }

  async function saveRole(payload: { name: string; description: string; permission_ids: number[] }, id?: number) {
    const { data } = id ? await apiClient.patch<Role>(`access/roles/${id}/`, payload) : await apiClient.post<Role>('access/roles/', payload)
    upsert(roles.value, data)
    // Counts shown on the permissions tab depend on role membership.
    const permissionResponse = await apiClient.get<Permission[]>('access/permissions/')
    permissions.value = permissionResponse.data
    return data
  }

  async function deleteRole(id: number) {
    await apiClient.delete(`access/roles/${id}/`)
    roles.value = roles.value.filter((r) => r.id !== id)
    users.value = users.value.map((user) => ({ ...user, role_ids: user.role_ids.filter((rid) => rid !== id) }))
  }

  async function saveUser(payload: UserPayload, id?: number) {
    const { data } = id ? await apiClient.patch<ManagedUser>(`access/users/${id}/`, payload) : await apiClient.post<ManagedUser>('access/users/', payload)
    upsert(users.value, data)
    const roleResponse = await apiClient.get<Role[]>('access/roles/')
    roles.value = roleResponse.data
    return data
  }

  return { catalog, permissions, roles, users, actionCount, fetchCatalog, fetchAll, savePermission, deletePermission, saveRole, deleteRole, saveUser }
})

// DRF answers a validation failure as {field: [messages]} or {detail}; this
// flattens either into one line a form can show.
export function apiErrorMessage(error: any, fallback: string): string {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return String(data.detail)
  const parts = Object.entries(data).map(([field, messages]) => {
    const text = Array.isArray(messages) ? messages.join(' ') : String(messages)
    return field === 'non_field_errors' ? text : `${field}: ${text}`
  })
  return parts.join(' ') || fallback
}
