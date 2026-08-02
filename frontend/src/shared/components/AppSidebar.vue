<script setup lang="ts">
import {
  ArchiveBoxIcon,
  BanknotesIcon,
  BookOpenIcon,
  BuildingOffice2Icon,
  CalendarDaysIcon,
  ChartBarIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ChevronDownIcon,
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
import { reactive, ref } from 'vue'
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

interface NavGroup {
  id: string
  labelKey: string
  items: NavItem[]
}

// REQ-CORE-UX-005 (docs/feedback.md "Feedback 1": "Sol panel çok kalabalık,
// öğeleri gruplayalım") -- related screens live under a collapsible section
// instead of one flat list that grows with every package a tenant activates.
// Dashboard stays outside any group since it's the one item every tenant
// always wants one click away.
const dashboardItem: NavItem = { to: '/', labelKey: 'nav.dashboard', icon: HomeIcon }

const navGroups: NavGroup[] = [
  {
    id: 'finance',
    labelKey: 'nav.groups.finance',
    items: [
      { to: '/entities', labelKey: 'nav.entities', icon: BuildingOffice2Icon },
      { to: '/accounts', labelKey: 'nav.accounts', icon: BookOpenIcon },
      { to: '/journal-entries', labelKey: 'nav.journalEntries', icon: DocumentTextIcon },
      { to: '/trial-balance', labelKey: 'nav.trialBalance', icon: ScaleIcon },
      { to: '/parties', labelKey: 'nav.parties', icon: UsersIcon },
      { to: '/invoices', labelKey: 'nav.invoices', icon: BanknotesIcon },
      { to: '/bills', labelKey: 'nav.bills', icon: ReceiptRefundIcon },
      { to: '/aging', labelKey: 'nav.aging', icon: ClockIcon },
    ],
  },
  {
    id: 'inventory',
    labelKey: 'nav.groups.inventory',
    items: [
      { to: '/items', labelKey: 'nav.items', icon: CubeIcon },
      { to: '/warehouses', labelKey: 'nav.warehouses', icon: ArchiveBoxIcon, package: 'inventory' },
      { to: '/stock-levels', labelKey: 'nav.stockLevels', icon: ChartBarIcon, package: 'inventory' },
      { to: '/purchase-orders', labelKey: 'nav.purchaseOrders', icon: ShoppingCartIcon, package: 'purchasing' },
    ],
  },
  {
    id: 'sales',
    labelKey: 'nav.groups.sales',
    items: [
      { to: '/leads', labelKey: 'nav.leads', icon: UserPlusIcon, package: 'sales_crm' },
      { to: '/sales-orders', labelKey: 'nav.salesOrders', icon: TruckIcon, package: 'sales_crm' },
    ],
  },
  {
    id: 'manufacturing',
    labelKey: 'nav.groups.manufacturing',
    items: [
      { to: '/boms', labelKey: 'nav.boms', icon: ClipboardDocumentListIcon, package: 'manufacturing' },
      { to: '/work-orders', labelKey: 'nav.workOrders', icon: CogIcon, package: 'manufacturing' },
    ],
  },
  {
    id: 'hr',
    labelKey: 'nav.groups.hr',
    items: [
      { to: '/employees', labelKey: 'nav.employees', icon: UserGroupIcon, package: 'hr_payroll' },
      { to: '/leave-requests', labelKey: 'nav.leaveRequests', icon: CalendarDaysIcon, package: 'hr_payroll' },
      { to: '/payroll-runs', labelKey: 'nav.payrollRuns', icon: CurrencyDollarIcon, package: 'hr_payroll' },
    ],
  },
]

const GROUP_STATE_KEY = 'sidebar-group-collapsed'
const storedGroupState = JSON.parse(localStorage.getItem(GROUP_STATE_KEY) ?? '{}')
const groupCollapsed = reactive<Record<string, boolean>>(
  Object.fromEntries(navGroups.map((g) => [g.id, storedGroupState[g.id] ?? false])),
)

function toggleGroup(id: string) {
  groupCollapsed[id] = !groupCollapsed[id]
  localStorage.setItem(GROUP_STATE_KEY, JSON.stringify(groupCollapsed))
}

function visible(item: NavItem) {
  return !item.package || tenant.hasPackage(item.package)
}

function groupVisible(group: NavGroup) {
  return group.items.some(visible)
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

    <nav class="flex-1 space-y-1 overflow-y-auto py-2">
      <RouterLink
        :to="dashboardItem.to"
        class="mx-2 flex items-center gap-3 rounded px-2 py-2 text-sm text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
        active-class="!bg-blue-50 !text-blue-700 dark:!bg-blue-950 dark:!text-blue-300"
        :title="collapsed ? t(dashboardItem.labelKey) : undefined"
      >
        <component :is="dashboardItem.icon" class="h-5 w-5 shrink-0" />
        <span v-if="!collapsed" class="truncate">{{ t(dashboardItem.labelKey) }}</span>
      </RouterLink>

      <div v-for="group in navGroups" :key="group.id">
        <template v-if="groupVisible(group)">
          <button
            v-if="!collapsed"
            class="mx-2 mt-2 flex w-[calc(100%-1rem)] items-center justify-between px-2 py-1 text-xs font-semibold uppercase tracking-wide text-neutral-400 hover:text-neutral-600 dark:text-neutral-500 dark:hover:text-neutral-300"
            @click="toggleGroup(group.id)"
          >
            <span>{{ t(group.labelKey) }}</span>
            <ChevronDownIcon class="h-3.5 w-3.5 transition-transform" :class="groupCollapsed[group.id] ? '-rotate-90' : ''" />
          </button>
          <div v-show="collapsed || !groupCollapsed[group.id]" class="space-y-0.5">
            <template v-for="item in group.items" :key="item.to">
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
          </div>
        </template>
      </div>
    </nav>
  </aside>
</template>
