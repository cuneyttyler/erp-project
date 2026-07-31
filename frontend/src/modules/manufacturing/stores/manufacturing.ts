import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface BOMLineInput {
  component_item: number
  quantity_per: string
}

export interface BOMLine extends BOMLineInput {
  id: number
  component_sku: string
  component_name: string
}

export interface BOM {
  id: number
  item: number
  item_sku: string
  item_name: string
  name: string
  is_active: boolean
  lines: BOMLine[]
  created_at: string
}

export type WOStatus = 'draft' | 'released' | 'in_progress' | 'completed' | 'cancelled'

export interface WorkOrder {
  id: number
  bom: number
  bom_item_sku: string
  bom_item_name: string
  warehouse: number
  warehouse_code: string
  quantity_planned: string
  quantity_completed: string
  quantity_remaining: string
  status: WOStatus
  scheduled_date: string
  memo: string
  created_at: string
}

// Manufacturing package state (REQ-MFG-001/002) -- src/modules/manufacturing/,
// a real independently-priced Package (product.md §6.2).
export const useManufacturingStore = defineStore('manufacturing', () => {
  const boms = ref<BOM[]>([])
  const workOrders = ref<WorkOrder[]>([])

  async function fetchBOMs() {
    const { data } = await apiClient.get('manufacturing/boms/', { params: { page_size: 100 } })
    boms.value = data.results ?? data
  }

  async function createBOM(item: number, name: string, lines: BOMLineInput[]) {
    const { data } = await apiClient.post<BOM>('manufacturing/boms/', { item, name, lines })
    boms.value.unshift(data)
    return data
  }

  async function fetchWorkOrders() {
    const { data } = await apiClient.get('manufacturing/work-orders/', { params: { page_size: 50 } })
    workOrders.value = data.results ?? data
  }

  async function createWorkOrder(bom: number, warehouse: number, quantity_planned: string, scheduled_date: string) {
    const { data } = await apiClient.post<WorkOrder>('manufacturing/work-orders/', {
      bom,
      warehouse,
      quantity_planned,
      scheduled_date,
    })
    workOrders.value.unshift(data)
    return data
  }

  function replace(wo: WorkOrder) {
    const idx = workOrders.value.findIndex((w) => w.id === wo.id)
    if (idx !== -1) workOrders.value[idx] = wo
  }

  async function releaseWorkOrder(id: number) {
    const { data } = await apiClient.post<WorkOrder>(`manufacturing/work-orders/${id}/release/`)
    replace(data)
    return data
  }

  async function completeWorkOrder(id: number, quantity: string) {
    const { data } = await apiClient.post<WorkOrder>(`manufacturing/work-orders/${id}/complete/`, { quantity })
    replace(data)
    return data
  }

  return {
    boms,
    workOrders,
    fetchBOMs,
    createBOM,
    fetchWorkOrders,
    createWorkOrder,
    releaseWorkOrder,
    completeWorkOrder,
  }
})
