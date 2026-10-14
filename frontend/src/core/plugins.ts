import {
  BanknotesIcon,
  BookOpenIcon,
  BuildingOffice2Icon,
  ClockIcon,
  CubeIcon,
  DocumentTextIcon,
  ReceiptRefundIcon,
  ScaleIcon,
  UsersIcon,
} from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

// The plugins that ship with Core (product.md §6.1) -- no subscription
// package gates them, but a tenant can still remove one it doesn't use.
export const corePlugins: PluginManifest[] = [
  {
    key: 'entities',
    icon: BuildingOffice2Icon,
    navGroup: 'finance',
    pages: [
      { path: '/entities', action: 'entity.view', name: 'entities', labelKey: 'nav.entities', icon: BuildingOffice2Icon, component: () => import('@/core/views/EntitiesView.vue') },
    ],
  },
  {
    key: 'general_ledger',
    icon: BookOpenIcon,
    navGroup: 'finance',
    pages: [
      { path: '/accounts', action: 'account.view', name: 'accounts', labelKey: 'nav.accounts', icon: BookOpenIcon, component: () => import('@/core/views/ChartOfAccountsView.vue') },
      { path: '/journal-entries', action: 'journal_entry.view', name: 'journal-entries', labelKey: 'nav.journalEntries', icon: DocumentTextIcon, component: () => import('@/core/views/JournalEntriesView.vue') },
      { path: '/trial-balance', action: 'trial_balance.view', name: 'trial-balance', labelKey: 'nav.trialBalance', icon: ScaleIcon, component: () => import('@/core/views/TrialBalanceView.vue') },
    ],
  },
  {
    key: 'receivables_payables',
    icon: BanknotesIcon,
    navGroup: 'finance',
    pages: [
      { path: '/parties', action: 'party.view', name: 'parties', labelKey: 'nav.parties', icon: UsersIcon, component: () => import('@/core/views/PartiesView.vue') },
      { path: '/invoices', action: 'invoice.view', name: 'invoices', labelKey: 'nav.invoices', icon: BanknotesIcon, component: () => import('@/core/views/InvoicesView.vue') },
      { path: '/bills', action: 'bill.view', name: 'bills', labelKey: 'nav.bills', icon: ReceiptRefundIcon, component: () => import('@/core/views/BillsView.vue') },
      { path: '/aging', action: 'ar_aging.view', name: 'aging', labelKey: 'nav.aging', icon: ClockIcon, component: () => import('@/core/views/AgingView.vue') },
    ],
  },
  {
    key: 'item_catalog',
    icon: CubeIcon,
    navGroup: 'inventory',
    pages: [
      { path: '/items', action: 'item.view', name: 'items', labelKey: 'nav.items', icon: CubeIcon, component: () => import('@/core/views/ItemsView.vue') },
    ],
  },
]
