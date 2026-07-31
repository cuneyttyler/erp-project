<script setup lang="ts">
import {
  ArchiveBoxIcon,
  BanknotesIcon,
  BookOpenIcon,
  CalendarDaysIcon,
  ChartBarIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  CogIcon,
  CubeIcon,
  CurrencyDollarIcon,
  DocumentTextIcon,
  HomeIcon,
  ReceiptRefundIcon,
  ScaleIcon,
  ShoppingCartIcon,
  TruckIcon,
  UserGroupIcon,
  UserPlusIcon,
  UsersIcon,
} from '@heroicons/vue/24/outline'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useTenantStore, type PackageKey } from '@/shared/stores/tenant'

// Collapsible left nav (replaces the old header-row nav). Collapse state
// persists across sessions since re-collapsing on every reload would be
// annoying for anyone who deliberately narrowed it for screen space.
const COLLAPSE_KEY = 'sidebar-collapsed'
const collapsed = ref(localStorage.getItem(COLLAPSE_KEY) === 'true')

function toggle() {
  collapsed.value = !collapsed.value
  localStorage.setItem(COLLAPSE_KEY, String(collapsed.value))
}

const tenant = useTenantStore()
const { t } = useI18n()

interface NavItem {
  to: string
  labelKey: string
  icon: typeof HomeIcon
  package?: PackageKey
}

// Core items ship for every tenant; package-gated items only render once
// tenant.hasPackage confirms the tenant actually purchased that package
// (technical.md §10.1) -- mirrors the router guard, doesn't replace it.
const navItems: NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', icon: HomeIcon },
  { to: '/accounts', labelKey: 'nav.accounts', icon: BookOpenIcon },
  { to: '/items', labelKey: 'nav.items', icon: CubeIcon },
  { to: '/journal-entries', labelKey: 'nav.journalEntries', icon: DocumentTextIcon },
  { to: '/trial-balance', labelKey: 'nav.trialBalance', icon: ScaleIcon },
  { to: '/parties', labelKey: 'nav.parties', icon: UsersIcon },
  { to: '/invoices', labelKey: 'nav.invoices', icon: BanknotesIcon },
  { to: '/bills', labelKey: 'nav.bills', icon: ReceiptRefundIcon },
  { to: '/aging', labelKey: 'nav.aging', icon: ClockIcon },
  { to: '/warehouses', labelKey: 'nav.warehouses', icon: ArchiveBoxIcon, package: 'inventory' },
  { to: '/stock-levels', labelKey: 'nav.stockLevels', icon: ChartBarIcon, package: 'inventory' },
  { to: '/purchase-orders', labelKey: 'nav.purchaseOrders', icon: ShoppingCartIcon, package: 'purchasing' },
  { to: '/leads', labelKey: 'nav.leads', icon: UserPlusIcon, package: 'sales_crm' },
  { to: '/sales-orders', labelKey: 'nav.salesOrders', icon: TruckIcon, package: 'sales_crm' },
  { to: '/boms', labelKey: 'nav.boms', icon: ClipboardDocumentListIcon, package: 'manufacturing' },
  { to: '/work-orders', labelKey: 'nav.workOrders', icon: CogIcon, package: 'manufacturing' },
  { to: '/employees', labelKey: 'nav.employees', icon: UserGroupIcon, package: 'hr_payroll' },
  { to: '/leave-requests', labelKey: 'nav.leaveRequests', icon: CalendarDaysIcon, package: 'hr_payroll' },
  { to: '/payroll-runs', labelKey: 'nav.payrollRuns', icon: CurrencyDollarIcon, package: 'hr_payroll' },
]

function visible(item: NavItem) {
  return !item.package || tenant.hasPackage(item.package)
}
</script>

<template>
  <aside
    class="flex h-full flex-col border-r border-neutral-200 bg-white transition-[width] duration-150 dark:border-neutral-800 dark:bg-neutral-900"
    :class="collapsed ? 'w-14' : 'w-56'"
  >
    <div class="flex items-center justify-between border-b border-neutral-200 px-3 py-3 dark:border-neutral-800">
      <span
        v-if="!collapsed"
        class="truncate text-sm font-semibold text-neutral-900 dark:text-neutral-100"
      >
        {{ t('app.name') }}
      </span>
      <button
        class="ml-auto rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
        :aria-label="collapsed ? 'Expand menu' : 'Collapse menu'"
        @click="toggle"
      >
        <ChevronDoubleRightIcon v-if="collapsed" class="h-4 w-4" />
        <ChevronDoubleLeftIcon v-else class="h-4 w-4" />
      </button>
    </div>

    <nav class="flex-1 space-y-0.5 overflow-y-auto py-2">
      <template v-for="item in navItems" :key="item.to">
        <RouterLink
          v-if="visible(item)"
          :to="item.to"
          class="mx-2 flex items-center gap-3 rounded px-2 py-2 text-sm text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
          active-class="!bg-blue-50 !text-blue-700 dark:!bg-blue-950 dark:!text-blue-300"
          :title="collapsed ? t(item.labelKey) : undefined"
        >
          <component :is="item.icon" class="h-5 w-5 shrink-0" />
          <span v-if="!collapsed" class="truncate">{{ t(item.labelKey) }}</span>
        </RouterLink>
      </template>
    </nav>
  </aside>
</template>
