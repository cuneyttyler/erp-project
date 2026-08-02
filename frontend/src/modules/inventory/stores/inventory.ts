import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Warehouse {
  id: number
  code: string
  name: string
  is_active: boolean
}

export interface StockLevelRow {
  item_sku: string
  item_name: string
  warehouse_code: string
  warehouse_name: string
  quantity_on_hand: string
}

// Inventory package state (REQ-INV-001/002). Lives under src/modules/ (not
// src/core/) because this is a real, independently-priced Package
// (product.md §6.2) -- its routes are only registered for tenants whose
// active_packages includes 'inventory' (technical.md §10.1).
export const useInventoryStore = defineStore('inventory', () => {
  const warehouses = ref<Warehouse[]>([])
  const stockLevels = ref<StockLevelRow[]>([])

  async function fetchWarehouses() {
    const { data } = await apiClient.get('inventory/warehouses/', { params: { page_size: 200 } })
    warehouses.value = data.results ?? data
  }

  async function createWarehouse(code: string, name: string) {
    const { data } = await apiClient.post<Warehouse>('inventory/warehouses/', { code, name })
    warehouses.value.push(data)
    return data
  }

  async function updateWarehouse(id: number, payload: Partial<Warehouse>) {
    const { data } = await apiClient.patch<Warehouse>(`inventory/warehouses/${id}/`, payload)
    const idx = warehouses.value.findIndex((w) => w.id === id)
    if (idx !== -1) warehouses.value[idx] = data
    return data
  }

  async function fetchStockLevels() {
    const { data } = await apiClient.get<StockLevelRow[]>('inventory/reports/stock-levels/')
    stockLevels.value = data
  }

  return { warehouses, stockLevels, fetchWarehouses, createWarehouse, updateWarehouse, fetchStockLevels }
})
