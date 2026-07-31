import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Lead {
  id: number
  name: string
  party: number | null
  party_name: string
  status: 'new' | 'qualified' | 'won' | 'lost'
  source: string
  notes: string
  created_at: string
}

export interface SOLineInput {
  item: number
  quantity_ordered: string
  unit_price: string
}

export interface SOLine extends SOLineInput {
  id: number
  item_sku: string
  item_name: string
  quantity_fulfilled: string
  quantity_remaining: string
  amount: string
}

export type SOStatus = 'draft' | 'confirmed' | 'partially_fulfilled' | 'fulfilled' | 'cancelled'

export interface SalesOrder {
  id: number
  party: number
  party_name: string
  warehouse: number
  warehouse_code: string
  order_date: string
  expected_date: string | null
  status: SOStatus
  memo: string
  lines: SOLine[]
  total: string
  created_at: string
}

// Sales & CRM package state (REQ-CRM-001/002/003) -- src/modules/sales_crm/,
// a real independently-priced Package (product.md §6.2).
export const useSalesCrmStore = defineStore('salesCrm', () => {
  const leads = ref<Lead[]>([])
  const orders = ref<SalesOrder[]>([])

  async function fetchLeads() {
    const { data } = await apiClient.get('sales-crm/leads/', { params: { page_size: 100 } })
    leads.value = data.results ?? data
  }

  async function createLead(payload: { name: string; source?: string; notes?: string }) {
    const { data } = await apiClient.post<Lead>('sales-crm/leads/', payload)
    leads.value.unshift(data)
    return data
  }

  function replaceLead(lead: Lead) {
    const idx = leads.value.findIndex((l) => l.id === lead.id)
    if (idx !== -1) leads.value[idx] = lead
  }

  async function qualifyLead(id: number) {
    const { data } = await apiClient.post<Lead>(`sales-crm/leads/${id}/qualify/`)
    replaceLead(data)
  }

  async function winLead(id: number, partyId: number) {
    const { data } = await apiClient.post<Lead>(`sales-crm/leads/${id}/mark_won/`, { party: partyId })
    replaceLead(data)
  }

  async function loseLead(id: number) {
    const { data } = await apiClient.post<Lead>(`sales-crm/leads/${id}/mark_lost/`)
    replaceLead(data)
  }

  async function fetchOrders() {
    const { data } = await apiClient.get('sales-crm/sales-orders/', { params: { page_size: 50 } })
    orders.value = data.results ?? data
  }

  async function createOrder(party: number, warehouse: number, order_date: string, lines: SOLineInput[]) {
    const { data } = await apiClient.post<SalesOrder>('sales-crm/sales-orders/', {
      party,
      warehouse,
      order_date,
      lines,
    })
    orders.value.unshift(data)
    return data
  }

  function replaceOrder(order: SalesOrder) {
    const idx = orders.value.findIndex((o) => o.id === order.id)
    if (idx !== -1) orders.value[idx] = order
  }

  async function confirmOrder(id: number) {
    const { data } = await apiClient.post<SalesOrder>(`sales-crm/sales-orders/${id}/confirm/`)
    replaceOrder(data)
    return data
  }

  async function fulfillOrder(id: number, lines: { line_id: number; quantity: string }[]) {
    const { data } = await apiClient.post(`sales-crm/sales-orders/${id}/fulfill/`, { lines })
    replaceOrder(data.sales_order)
    return data
  }

  return {
    leads,
    orders,
    fetchLeads,
    createLead,
    qualifyLead,
    winLead,
    loseLead,
    fetchOrders,
    createOrder,
    confirmOrder,
    fulfillOrder,
  }
})
