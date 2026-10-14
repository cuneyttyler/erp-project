<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { usePOSStore, type ZReport } from '@/modules/pos/stores/pos'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-POS-004: open/close a shift and produce its Z-report (cash/sales
// reconciliation -- see models.py's module docstring for what "Z-report"
// does and doesn't mean here, i.e. not the statutory fiscal-device format).
const pos = usePOSStore()

onMounted(() => {
  pos.fetchTills()
  pos.fetchShifts()
})

const openForm = reactive({ till: null as number | null, opening_cash: '0.00' })
const error = ref('')

async function openShift() {
  error.value = ''
  if (openForm.till === null) {
    error.value = t('shifts.errors.till')
    return
  }
  try {
    await pos.openShift(openForm.till, openForm.opening_cash)
    openForm.opening_cash = '0.00'
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('shifts.errors.open')
  }
}

const closingCash = reactive<Record<number, string>>({})
const zReports = reactive<Record<number, ZReport>>({})

async function closeShift(shiftId: number) {
  error.value = ''
  try {
    await pos.closeShift(shiftId, closingCash[shiftId] ?? '0.00')
    await showZReport(shiftId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('shifts.errors.close')
  }
}

async function showZReport(shiftId: number) {
  zReports[shiftId] = await pos.fetchZReport(shiftId)
}

const statusLabels = computed<Record<string, string>>(() => ({ open: t('widgets.status.open'), closed: t('widgets.status.closed') }))

const columns = computed<ColumnDef[]>(() => [
  { key: 'till_label', label: t('common.till') },
  { key: 'opened_by_username', label: t('shifts.openedBy') },
  { key: 'opening_cash', label: t('shifts.openingCash'), type: 'number' },
  { key: 'status', label: t('common.status') },
  { key: 'opened_at', label: t('shifts.openedAt') },
  { key: 'actions', label: '', sortable: false, filterable: false },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('shifts.title') }}</h1>
    <PageInsights screen-key="pos-shifts" :widgets="['pos_sales_trend','pos_sales_by_till','pos_payment_mix']" :follow="pos.shifts" />

    <form class="mt-4 flex max-w-xl items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="openShift">
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.till') }}</label>
        <select v-model.number="openForm.till" data-testid="pos-till-select" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.selectTill') }}</option>
          <option v-for="t in pos.tills" :key="t.id" :value="t.id">{{ t.store_code }}/{{ t.code }} — {{ t.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('shifts.openingCash') }}</label>
        <input v-model="openForm.opening_cash" data-testid="pos-opening-cash-input" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" data-testid="pos-open-shift-submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('shifts.open') }}</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-6">
      <DataTable screen-key="pos-shifts" :columns="columns" :rows="pos.shifts">
        <template #status="{ row }">{{ statusLabels[row.status] }}</template>
        <template #actions="{ row }">
          <div v-if="row.status === 'open'" class="flex items-center gap-1">
            <input v-model="closingCash[row.id]" :placeholder="t('shifts.countedCash')" class="w-24 rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800" />
            <button class="rounded bg-neutral-800 px-2 py-1 text-xs font-medium text-white hover:bg-neutral-900" @click="closeShift(row.id)">{{ t('common.close') }}</button>
          </div>
          <button v-else class="rounded bg-neutral-200 px-2 py-1 text-xs font-medium text-neutral-800 hover:bg-neutral-300 dark:bg-neutral-700 dark:text-neutral-100" @click="showZReport(row.id)">
            {{ t('shifts.zReport') }}
          </button>
        </template>
      </DataTable>
    </div>

    <div v-for="(report, shiftId) in zReports" :key="shiftId" class="mt-6 max-w-md rounded border border-neutral-200 p-4 dark:border-neutral-800">
      <h2 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{{ t('shifts.zReportFor', { id: report.shift_id }) }}</h2>
      <dl class="mt-2 space-y-1 text-sm">
        <div class="flex justify-between"><dt class="text-neutral-500">{{ t('shifts.transactions') }}</dt><dd>{{ report.transaction_count }}</dd></div>
        <div class="flex justify-between"><dt class="text-neutral-500">{{ t('shifts.grossSales') }}</dt><dd>{{ report.gross_sales }} ₺</dd></div>
        <div class="flex justify-between"><dt class="text-neutral-500">{{ t('shifts.returns') }}</dt><dd>{{ report.returns_total }} ₺</dd></div>
        <div class="flex justify-between font-medium"><dt>{{ t('shifts.netSales') }}</dt><dd>{{ report.net_sales }} ₺</dd></div>
        <div v-for="(amount, method) in report.by_payment_method" :key="method" class="flex justify-between text-neutral-500">
          <dt>{{ method === 'cash' ? 'Nakit' : 'Kart' }}</dt><dd>{{ amount }} ₺</dd>
        </div>
        <div class="flex justify-between"><dt class="text-neutral-500">{{ t('shifts.expectedCash') }}</dt><dd>{{ report.expected_cash }} ₺</dd></div>
        <div v-if="report.cash_discrepancy !== null" class="flex justify-between" :class="report.cash_discrepancy === '0.00' ? '' : 'text-red-600'">
          <dt>{{ t('shifts.cashDifference') }}</dt><dd>{{ report.cash_discrepancy }} ₺</dd>
        </div>
      </dl>
    </div>
  </section>
</template>
