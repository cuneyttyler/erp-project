import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Party {
  id: number
  name: string
  party_type: 'customer' | 'vendor' | 'both'
  tax_id: string
  email: string
  phone: string
  payment_terms_days: number
  is_active: boolean
}

export interface DocumentLineInput {
  description: string
  quantity: string
  unit_price: string
}

export interface DocumentLine extends DocumentLineInput {
  id: number
  amount: string
}

export type DocumentStatus = 'draft' | 'sent' | 'partially_paid' | 'paid' | 'cancelled'

export interface FinancialDocument {
  id: number
  party: number
  party_name: string
  issue_date: string
  due_date: string
  currency: string
  status: DocumentStatus
  memo: string
  lines: DocumentLine[]
  total: string
  amount_paid: string
  balance_due: string
  is_overdue: boolean
  created_at: string
}

export interface AgingRow {
  document_id: number
  party_name: string
  due_date: string
  balance_due: string
  days_overdue: number
  bucket: string
}

// AR/AP state (REQ-CORE-AR-*/AP-*). Core, not a package -- lives under
// src/core/ alongside the GL/COA store (technical.md §10.1).
export const useARAPStore = defineStore('arap', () => {
  const parties = ref<Party[]>([])
  const invoices = ref<FinancialDocument[]>([])
  const bills = ref<FinancialDocument[]>([])
  const arAging = ref<AgingRow[]>([])
  const apAging = ref<AgingRow[]>([])

  async function fetchParties() {
    const { data } = await apiClient.get('core/parties/', { params: { page_size: 200 } })
    parties.value = data.results ?? data
  }

  async function createParty(payload: Partial<Party>) {
    const { data } = await apiClient.post<Party>('core/parties/', payload)
    parties.value.unshift(data)
    return data
  }

  async function fetchInvoices() {
    const { data } = await apiClient.get('core/invoices/', { params: { page_size: 50 } })
    invoices.value = data.results ?? data
  }

  async function createInvoice(
    party: number,
    issue_date: string,
    due_date: string,
    memo: string,
    lines: DocumentLineInput[],
  ) {
    const { data } = await apiClient.post<FinancialDocument>('core/invoices/', {
      party,
      issue_date,
      due_date,
      memo,
      lines,
    })
    invoices.value.unshift(data)
    return data
  }

  async function sendInvoice(id: number) {
    const { data } = await apiClient.post<FinancialDocument>(`core/invoices/${id}/send_document/`)
    const idx = invoices.value.findIndex((d) => d.id === id)
    if (idx !== -1) invoices.value[idx] = data
    return data
  }

  async function payInvoice(id: number, amount: string, date: string) {
    await apiClient.post('core/payments/', { invoice: id, amount, date })
    const { data } = await apiClient.get<FinancialDocument>(`core/invoices/${id}/`)
    const idx = invoices.value.findIndex((d) => d.id === id)
    if (idx !== -1) invoices.value[idx] = data
    return data
  }

  async function fetchBills() {
    const { data } = await apiClient.get('core/bills/', { params: { page_size: 50 } })
    bills.value = data.results ?? data
  }

  async function createBill(
    party: number,
    issue_date: string,
    due_date: string,
    memo: string,
    lines: DocumentLineInput[],
  ) {
    const { data } = await apiClient.post<FinancialDocument>('core/bills/', {
      party,
      issue_date,
      due_date,
      memo,
      lines,
    })
    bills.value.unshift(data)
    return data
  }

  async function sendBill(id: number) {
    const { data } = await apiClient.post<FinancialDocument>(`core/bills/${id}/send_document/`)
    const idx = bills.value.findIndex((d) => d.id === id)
    if (idx !== -1) bills.value[idx] = data
    return data
  }

  async function payBill(id: number, amount: string, date: string) {
    await apiClient.post('core/payments/', { bill: id, amount, date })
    const { data } = await apiClient.get<FinancialDocument>(`core/bills/${id}/`)
    const idx = bills.value.findIndex((d) => d.id === id)
    if (idx !== -1) bills.value[idx] = data
    return data
  }

  async function fetchARAging() {
    const { data } = await apiClient.get<AgingRow[]>('core/reports/ar-aging/')
    arAging.value = data
  }

  async function fetchAPAging() {
    const { data } = await apiClient.get<AgingRow[]>('core/reports/ap-aging/')
    apAging.value = data
  }

  return {
    parties,
    invoices,
    bills,
    arAging,
    apAging,
    fetchParties,
    createParty,
    fetchInvoices,
    createInvoice,
    sendInvoice,
    payInvoice,
    fetchBills,
    createBill,
    sendBill,
    payBill,
    fetchARAging,
    fetchAPAging,
  }
})
