import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Account {
  id: number
  code: string
  name: string
  account_type: 'asset' | 'liability' | 'equity' | 'revenue' | 'expense'
  parent: number | null
  is_active: boolean
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
export const useLedgerStore = defineStore('ledger', () => {
  const accounts = ref<Account[]>([])
  const entries = ref<JournalEntry[]>([])
  const trialBalance = ref<TrialBalanceRow[]>([])

  // GL/COA endpoints live in apps/core, mounted at /api/v1/core/ (config/urls.py).
  async function fetchAccounts() {
    const { data } = await apiClient.get('core/accounts/', { params: { page_size: 200 } })
    accounts.value = data.results ?? data
  }

  async function updateAccount(id: number, payload: Partial<Account>) {
    const { data } = await apiClient.patch<Account>(`core/accounts/${id}/`, payload)
    const idx = accounts.value.findIndex((a) => a.id === id)
    if (idx !== -1) accounts.value[idx] = data
    return data
  }

  async function fetchEntries() {
    const { data } = await apiClient.get('core/journal-entries/', { params: { page_size: 50 } })
    entries.value = data.results ?? data
  }

  async function createEntry(date: string, memo: string, lines: JournalLineInput[]) {
    const { data } = await apiClient.post<JournalEntry>('core/journal-entries/', { date, memo, lines })
    entries.value.unshift(data)
    return data
  }

  async function postEntry(id: number) {
    const { data } = await apiClient.post<JournalEntry>(`core/journal-entries/${id}/post_entry/`)
    const idx = entries.value.findIndex((e) => e.id === id)
    if (idx !== -1) entries.value[idx] = data
    return data
  }

  async function fetchTrialBalance() {
    const { data } = await apiClient.get<TrialBalanceRow[]>('core/reports/trial-balance/')
    trialBalance.value = data
  }

  return {
    accounts,
    entries,
    trialBalance,
    fetchAccounts,
    updateAccount,
    fetchEntries,
    createEntry,
    postEntry,
    fetchTrialBalance,
  }
})
