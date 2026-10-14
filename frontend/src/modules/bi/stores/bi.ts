import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export type ChartKind = 'time' | 'category'
export type ChartType = 'bar' | 'line'

export interface AvailableSeries {
  name: string
  description: string
  input_schema: Record<string, unknown>
  chart_kind: ChartKind
}

export interface SeriesPoint {
  label: string
  value: string
}

export interface SavedReport {
  id: number
  name: string
  series_name: string
  chart_type: ChartType
  params: Record<string, unknown>
  owner_username: string
  is_shared: boolean
  created_at: string
}

export interface DashboardTile {
  id: number
  report: SavedReport
  position: number
}

export interface Dashboard {
  id: number
  name: string
  owner_username: string
  is_shared: boolean
  tiles: DashboardTile[]
  created_at: string
}

// Advanced BI package state (REQ-BI-001/002/003) -- src/modules/bi/, a real
// independently-priced Package (product.md §6.2, development-plan.md §6).
// REQ-BI-004 (anomaly detection) has no frontend state of its own here --
// it's a field on the existing Bill record (BillsView.vue), not a BI-owned
// screen.
export const useBIStore = defineStore('bi', () => {
  const availableSeries = ref<AvailableSeries[]>([])
  const reports = ref<SavedReport[]>([])
  const dashboards = ref<Dashboard[]>([])

  async function fetchAvailableSeries() {
    const { data } = await apiClient.get<AvailableSeries[]>('bi/series/')
    availableSeries.value = data
  }

  async function runSeries(seriesName: string, params: Record<string, unknown> = {}) {
    const { data } = await apiClient.post<{ chart_kind: ChartKind; series: SeriesPoint[] }>('bi/series/run/', {
      series_name: seriesName,
      params,
    })
    return data
  }

  async function fetchReports() {
    const { data } = await apiClient.get('bi/reports/', { params: { page_size: 100 } })
    reports.value = data.results ?? data
  }

  async function createReport(payload: { name: string; series_name: string; chart_type: ChartType; params?: Record<string, unknown>; is_shared?: boolean }) {
    const { data } = await apiClient.post<SavedReport>('bi/reports/', payload)
    reports.value.unshift(data)
    return data
  }

  async function fetchDashboards() {
    const { data } = await apiClient.get('bi/dashboards/', { params: { page_size: 50 } })
    dashboards.value = data.results ?? data
  }

  async function createDashboard(payload: { name: string; is_shared?: boolean }) {
    const { data } = await apiClient.post<Dashboard>('bi/dashboards/', payload)
    dashboards.value.unshift(data)
    return data
  }

  function replaceDashboard(dashboard: Dashboard) {
    const idx = dashboards.value.findIndex((d) => d.id === dashboard.id)
    if (idx !== -1) dashboards.value[idx] = dashboard
  }

  async function addTile(dashboardId: number, reportId: number) {
    await apiClient.post(`bi/dashboards/${dashboardId}/add-tile/`, { report_id: reportId })
    await fetchDashboards()
  }

  async function removeTile(dashboardId: number, tileId: number) {
    await apiClient.post(`bi/dashboards/${dashboardId}/remove-tile/`, { tile_id: tileId })
    await fetchDashboards()
  }

  async function reorderTiles(dashboardId: number, order: { tile_id: number; position: number }[]) {
    const { data } = await apiClient.post<Dashboard>(`bi/dashboards/${dashboardId}/reorder-tiles/`, order)
    replaceDashboard(data)
    return data
  }

  return {
    availableSeries,
    reports,
    dashboards,
    fetchAvailableSeries,
    runSeries,
    fetchReports,
    createReport,
    fetchDashboards,
    createDashboard,
    addTile,
    removeTile,
    reorderTiles,
  }
})
