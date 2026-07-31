import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface POLineInput {
  item: number
  quantity_ordered: string
  unit_price: string
}

export interface POLine extends POLineInput {
  id: number
  item_sku: string
  item_name: string
  quantity_received: string
  quantity_remaining: string
  amount: string
}

export type POStatus = 'draft' | 'sent' | 'partially_received' | 'received' | 'cancelled'

export interface PurchaseOrder {
  id: number
  party: number
  party_name: string
  warehouse: number
  warehouse_code: string
  order_date: string
  expected_date: string | null
  status: POStatus
  memo: string
  lines: POLine[]
  total: string
  requires_approval: boolean
  approved_at: string | null
  created_at: string
}

// Purchasing package state (REQ-PUR-001/002/005) -- src/modules/purchasing/,
// a real independently-priced Package (product.md §6.2).
export const usePurchasingStore = defineStore('purchasing', () => {
  const orders = ref<PurchaseOrder[]>([])

  async function fetchOrders() {
    const { data } = await apiClient.get('purchasing/purchase-orders/', { params: { page_size: 50 } })
    orders.value = data.results ?? data
  }

  async function createOrder(
    party: number,
    warehouse: number,
    order_date: string,
    lines: POLineInput[],
  ) {
    const { data } = await apiClient.post<PurchaseOrder>('purchasing/purchase-orders/', {
      party,
      warehouse,
      order_date,
      lines,
    })
    orders.value.unshift(data)
    return data
  }

  function replace(order: PurchaseOrder) {
    const idx = orders.value.findIndex((o) => o.id === order.id)
    if (idx !== -1) orders.value[idx] = order
  }

  async function approveOrder(id: number) {
    const { data } = await apiClient.post<PurchaseOrder>(`purchasing/purchase-orders/${id}/approve/`)
    replace(data)
    return data
  }

  async function sendOrder(id: number) {
    const { data } = await apiClient.post<PurchaseOrder>(`purchasing/purchase-orders/${id}/send_document/`)
    replace(data)
    return data
  }

  async function receiveOrder(id: number, lines: { line_id: number; quantity: string }[]) {
    const { data } = await apiClient.post(`purchasing/purchase-orders/${id}/receive/`, { lines })
    replace(data.purchase_order)
    return data
  }

  return { orders, fetchOrders, createOrder, approveOrder, sendOrder, receiveOrder }
})
