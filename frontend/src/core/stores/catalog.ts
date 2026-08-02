import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Item {
  id: number
  sku: string
  name: string
  unit_of_measure: string
  cost_method: 'fifo' | 'weighted_average'
  is_active: boolean
}

// Item is Core master data (technical.md §5: "shared by Inventory,
// Purchasing, Sales, Manufacturing"), not owned by any one package -- so
// this store lives under src/core/ alongside the GL/AR-AP stores, not under
// src/modules/inventory/ or src/modules/purchasing/.
export const useCatalogStore = defineStore('catalog', () => {
  const items = ref<Item[]>([])

  async function fetchItems() {
    const { data } = await apiClient.get('core/items/', { params: { page_size: 200 } })
    items.value = data.results ?? data
  }

  async function createItem(payload: Partial<Item>) {
    const { data } = await apiClient.post<Item>('core/items/', payload)
    items.value.unshift(data)
    return data
  }

  async function updateItem(id: number, payload: Partial<Item>) {
    const { data } = await apiClient.patch<Item>(`core/items/${id}/`, payload)
    const idx = items.value.findIndex((i) => i.id === id)
    if (idx !== -1) items.value[idx] = data
    return data
  }

  return { items, fetchItems, createItem, updateItem }
})
