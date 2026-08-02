import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'
import { useEntityStore } from '@/shared/stores/entity'

export interface Account {
  id: number
  entity: number
  code: string
  name: string
  account_type: 'asset' | 'liability' | 'equity' | 'revenue' | 'expense'
  parent: number | null
  is_active: boolean
  is_intercompany: boolean
}

export interface JournalLineInput {
  account: number
  debit: string
  credit: string
  description?: string
}

export interface JournalLine extends JournalLineInput {
  id: number
  account_code: string
  account_name: string
}

export interface JournalEntry {
  id: number
  entity: number
  date: string
  memo: string
  status: 'draft' | 'posted'
  lines: JournalLine[]
  created_by_username: string | null
  posted_at: string | null
  created_at: string
}

export interface TrialBalanceRow {
  code: string
  name: string
  account_type: string
  total_debit: string
  total_credit: string
}

// Core GL/COA state (REQ-CORE-GL-*). This is Core, not a Package, so it lives
// under src/core/ rather than src/modules/<package>/ (technical.md §10.1
// reserves modules/ for the independently-priced packages).
//
// REQ-CORE-ENT-001: every fetch/create here is scoped to
// useEntityStore().currentEntityId -- the globally-selected "current
// entity" (App.vue's header switcher), not a per-screen selector. Trial
// balance is the one exception: it also supports an explicit consolidated
// mode independent of the current-entity selection (see fetchTrialBalance).
export const useLedgerStore = defineStore('ledger', () => {
  const accounts = ref<Account[]>([])
  const entries = ref<JournalEntry[]>([])
  const trialBalance = ref<TrialBalanceRow[]>([])

  // GL/COA endpoints live in apps/core, mounted at /api/v1/core/ (config/urls.py).
  async function fetchAccounts() {
    const entity = useEntityStore().currentEntityId
    const { data } = await apiClient.get('core/accounts/', { params: { page_size: 200, entity } })
    accounts.value = data.results ?? data
  }

  async function createAccount(payload: { code: string; name: string; account_type: Account['account_type'] }) {
    const entity = useEntityStore().currentEntityId
    const { data } = await apiClient.post<Account>('core/accounts/', { ...payload, entity })
    accounts.value.push(data)
    return data
  }

  async function updateAccount(id: number, payload: Partial<Account>) {
    const { data } = await apiClient.patch<Account>(`core/accounts/${id}/`, payload)
    const idx = accounts.value.findIndex((a) => a.id === id)
    if (idx !== -1) accounts.value[idx] = data
    return data
  }

  async function fetchEntries() {
    const entity = useEntityStore().currentEntityId
    const { data } = await apiClient.get('core/journal-entries/', { params: { page_size: 50, entity } })
    entries.value = data.results ?? data
  }

  async function createEntry(date: string, memo: string, lines: JournalLineInput[]) {
    const entity = useEntityStore().currentEntityId
    const { data } = await apiClient.post<JournalEntry>('core/journal-entries/', { entity, date, memo, lines })
    entries.value.unshift(data)
    return data
  }

  async function postEntry(id: number) {
    const { data } = await apiClient.post<JournalEntry>(`core/journal-entries/${id}/post_entry/`)
    const idx = entries.value.findIndex((e) => e.id === id)
    if (idx !== -1) entries.value[idx] = data
    return data
  }

  // `mode`: a specific entity id for a single-entity trial balance, or the
  // literal 'consolidated' for the cross-entity summed view (backend §
  // REQ-CORE-ENT-002 -- intercompany-flagged accounts excluded server-side).
  async function fetchTrialBalance(mode: number | 'consolidated') {
    const params = mode === 'consolidated' ? { consolidated: 'true' } : { entity: mode }
    const { data } = await apiClient.get<TrialBalanceRow[]>('core/reports/trial-balance/', { params })
    trialBalance.value = data
  }

  return {
    accounts,
    entries,
    trialBalance,
    fetchAccounts,
    createAccount,
    updateAccount,
    fetchEntries,
    createEntry,
    postEntry,
    fetchTrialBalance,
  }
})
