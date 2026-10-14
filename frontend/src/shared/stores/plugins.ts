import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { pluginsByKey } from '@/plugins/registry'
import { apiClient } from '@/shared/api/client'
import { useTenantStore } from '@/shared/stores/tenant'

export interface PluginState {
  key: string
  package: string | null
  // In the tenant's subscription (Core plugins always are).
  is_licensed: boolean
  // Not removed by the tenant.
  is_enabled: boolean
  is_active: boolean
  widget_count: number
}

export type WidgetKind = 'stat' | 'chart' | 'table' | 'attention' | 'quick_actions'
export type WidgetSize = 'sm' | 'md' | 'lg'

export interface WidgetState {
  key: string
  // null = a system widget, available whatever plugins are installed.
  plugin: string | null
  kind: WidgetKind
  default_size: WidgetSize
  size: WidgetSize
  is_enabled: boolean
  // Its plugin is active -- a widget can be enabled yet unavailable while
  // its plugin is removed, and comes back when the plugin does.
  is_available: boolean
}

// Which plugins this tenant has installed (tenant-wide) and how this user
// has arranged their home panel (per user). Loaded once per session by the
// router guard, before the first guarded navigation resolves.
export const usePluginStore = defineStore('plugins', () => {
  const plugins = ref<PluginState[]>([])
  const widgets = ref<WidgetState[]>([])
  const canManage = ref(false)
  const isLoaded = ref(false)

  const stateByKey = computed(() => Object.fromEntries(plugins.value.map((p) => [p.key, p])))

  const isActive = computed(() => (key: string) => {
    const state = stateByKey.value[key]
    if (state) return state.is_active
    // No server state (the load failed): fall back to the subscription
    // alone rather than hiding the whole app behind a failed request.
    const pkg = pluginsByKey[key]?.package
    return !pkg || useTenantStore().hasPackage(pkg)
  })

  const panelWidgets = computed(() => widgets.value.filter((w) => w.is_enabled && w.is_available))

  async function load() {
    const [pluginResponse, widgetResponse] = await Promise.all([
      apiClient.get<{ can_manage: boolean; plugins: PluginState[] }>('plugins/'),
      apiClient.get<WidgetState[]>('plugins/widgets/'),
    ])
    plugins.value = pluginResponse.data.plugins
    canManage.value = pluginResponse.data.can_manage
    widgets.value = widgetResponse.data
    isLoaded.value = true
  }

  function reset() {
    plugins.value = []
    widgets.value = []
    canManage.value = false
    isLoaded.value = false
  }

  async function setPluginEnabled(key: string, isEnabled: boolean) {
    const { data } = await apiClient.patch<PluginState>(`plugins/${key}/`, { is_enabled: isEnabled })
    const idx = plugins.value.findIndex((p) => p.key === key)
    if (idx !== -1) plugins.value[idx] = data
    // Widget availability follows the plugin.
    const widgetResponse = await apiClient.get<WidgetState[]>('plugins/widgets/')
    widgets.value = widgetResponse.data
  }

  // Applies the new arrangement immediately and persists it; the list's
  // order is the panel's order.
  async function saveLayout(next: WidgetState[]) {
    const previous = widgets.value
    widgets.value = next
    try {
      const { data } = await apiClient.put<WidgetState[]>('plugins/widgets/layout/', {
        widgets: next.map((w) => ({ key: w.key, is_enabled: w.is_enabled, size: w.size })),
      })
      widgets.value = data
    } catch (error) {
      widgets.value = previous
      throw error
    }
  }

  async function resetLayout() {
    const { data } = await apiClient.post<WidgetState[]>('plugins/widgets/layout/reset/')
    widgets.value = data
  }

  return { plugins, widgets, canManage, isLoaded, stateByKey, isActive, panelWidgets, load, reset, setPluginEnabled, saveLayout, resetLayout }
})
