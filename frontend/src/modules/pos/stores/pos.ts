import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Store {
  id: number
  entity: number
  entity_code: string
  warehouse: number
  warehouse_code: string
  code: string
  name: string
  is_active: boolean
}

export interface Till {
  id: number
  store: number
  store_code: string
  code: string
  name: string
  is_active: boolean
}

export type ShiftStatus = 'open' | 'closed'

export interface Shift {
  id: number
  till: number
  till_label: string
  opened_by_username: string
  opening_cash: string
  closing_cash_counted: string | null
  status: ShiftStatus
  opened_at: string
  closed_at: string | null
}

export interface ZReport {
  shift_id: number
  till: string
  status: ShiftStatus
  opened_at: string
  closed_at: string | null
  transaction_count: number
  gross_sales: string
  returns_total: string
  net_sales: string
  by_payment_method: Record<string, string>
  opening_cash: string
  expected_cash: string
  closing_cash_counted: string | null
  cash_discrepancy: string | null
}

export type PaymentMethod = 'cash' | 'card'

export interface SaleLine {
  id: number
  item: number
  item_sku: string
  item_name: string
  quantity: string
  unit_price: string
  discount_amount: string
  quantity_returned: string
  line_total: string
}

export interface Payment {
  id: number
  method: PaymentMethod
  amount: string
}

export type SaleStatus = 'completed' | 'partially_returned' | 'returned'

export interface Sale {
  id: number
  shift: number
  status: SaleStatus
  client_reference: string | null
  created_by_username: string
  journal_entry: number | null
  lines: SaleLine[]
  payments: Payment[]
  subtotal: string
  created_at: string
}

export interface CheckoutLineInput {
  item_id: number
  quantity: string
  unit_price: string
  discount_amount?: string
}

export interface CheckoutPaymentInput {
  method: PaymentMethod
  amount: string
}

// POS module state (REQ-POS-001/002/004/005) -- src/modules/pos/, a real
// independently-priced Package (product.md §6.2, development-plan.md §6).
export const usePOSStore = defineStore('pos', () => {
  const stores = ref<Store[]>([])
  const tills = ref<Till[]>([])
  const shifts = ref<Shift[]>([])
  const sales = ref<Sale[]>([])

  async function fetchStores() {
    const { data } = await apiClient.get('pos/stores/', { params: { page_size: 100 } })
    stores.value = data.results ?? data
  }

  async function createStore(payload: { entity: number; warehouse: number; code: string; name: string }) {
    const { data } = await apiClient.post<Store>('pos/stores/', payload)
    stores.value.unshift(data)
    return data
  }

  async function fetchTills() {
    const { data } = await apiClient.get('pos/tills/', { params: { page_size: 100 } })
    tills.value = data.results ?? data
  }

  async function createTill(payload: { store: number; code: string; name: string }) {
    const { data } = await apiClient.post<Till>('pos/tills/', payload)
    tills.value.unshift(data)
    return data
  }

  async function fetchShifts() {
    const { data } = await apiClient.get('pos/shifts/', { params: { page_size: 50 } })
    shifts.value = data.results ?? data
  }

  function replaceShift(shift: Shift) {
    const idx = shifts.value.findIndex((s) => s.id === shift.id)
    if (idx !== -1) shifts.value[idx] = shift
    else shifts.value.unshift(shift)
  }

  async function openShift(till: number, opening_cash: string) {
    const { data } = await apiClient.post<Shift>('pos/shifts/', { till, opening_cash })
    replaceShift(data)
    return data
  }

  async function closeShift(shiftId: number, closing_cash_counted: string) {
    const { data } = await apiClient.post<Shift>(`pos/shifts/${shiftId}/close/`, { closing_cash_counted })
    replaceShift(data)
    return data
  }

  async function fetchZReport(shiftId: number) {
    const { data } = await apiClient.get<ZReport>(`pos/shifts/${shiftId}/z-report/`)
    return data
  }

  async function checkout(
    shiftId: number,
    lines: CheckoutLineInput[],
    payments: CheckoutPaymentInput[],
    clientReference?: string,
  ) {
    const { data } = await apiClient.post<Sale>(`pos/shifts/${shiftId}/checkout/`, {
      lines,
      payments,
      client_reference: clientReference ?? '',
    })
    sales.value.unshift(data)
    return data
  }

  async function fetchSales(shiftId?: number) {
    const { data } = await apiClient.get('pos/sales/', { params: { page_size: 50, shift: shiftId } })
    sales.value = data.results ?? data
  }

  async function returnSale(
    saleId: number,
    lines: { sale_line_id: number; quantity: string }[],
    refund_method: PaymentMethod,
    reason?: string,
  ) {
    const { data } = await apiClient.post(`pos/sales/${saleId}/return/`, { lines, refund_method, reason: reason ?? '' })
    return data
  }

  return {
    stores,
    tills,
    shifts,
    sales,
    fetchStores,
    createStore,
    fetchTills,
    createTill,
    fetchShifts,
    openShift,
    closeShift,
    fetchZReport,
    checkout,
    fetchSales,
    returnSale,
  }
})
