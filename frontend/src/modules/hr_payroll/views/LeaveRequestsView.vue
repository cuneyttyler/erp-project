<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useHrPayrollStore, type LeaveType } from '@/modules/hr_payroll/stores/hrPayroll'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-HR-002: leave request/approval workflow.
const hrPayroll = useHrPayrollStore()

onMounted(() => {
  hrPayroll.fetchEmployees()
  hrPayroll.fetchLeaveRequests()
})

const form = reactive({
  employee: null as number | null,
  leave_type: 'annual' as LeaveType,
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  reason: '',
})
const error = ref('')

async function submit() {
  error.value = ''
  if (form.employee === null) {
    error.value = t('leave.errors.employee')
    return
  }
  try {
    await hrPayroll.createLeaveRequest({ ...form, employee: form.employee })
    form.reason = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('leave.errors.create')
  }
}

async function approve(id: number) {
  try {
    await hrPayroll.approveLeaveRequest(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('leave.errors.approve')
  }
}

async function reject(id: number) {
  try {
    await hrPayroll.rejectLeaveRequest(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('leave.errors.reject')
  }
}

const statusLabels = computed<Record<string, string>>(() => ({
  pending: t('widgets.status.pending'),
  approved: t('widgets.status.approved'),
  rejected: t('widgets.status.rejected'),
}))
const leaveTypeLabels = computed<Record<string, string>>(() => ({
  annual: t('widgets.status.annual'),
  sick: t('widgets.status.sick'),
}))

const columns = computed<ColumnDef[]>(() => [
  { key: 'employee_name', label: t('common.employee') },
  { key: 'leave_type', label: t('common.type'), formatter: (row) => leaveTypeLabels.value[row.leave_type] ?? row.leave_type },
  { key: 'start_date', label: t('common.start') },
  { key: 'end_date', label: t('common.end') },
  { key: 'days', label: t('common.days'), type: 'number' },
  { key: 'status', label: t('common.status') },
  { key: 'actions', label: '', sortable: false, filterable: false },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('leave.title') }}</h1>
    <PageInsights screen-key="leave-requests" :widgets="['leave_days_trend']" :follow="hrPayroll.leaveRequests" />

    <form class="mt-4 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <select v-model.number="form.employee" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
        <option :value="null" disabled>{{ t('common.selectEmployee') }}</option>
        <option v-for="e in hrPayroll.employees" :key="e.id" :value="e.id">{{ e.first_name }} {{ e.last_name }}</option>
      </select>
      <select v-model="form.leave_type" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
        <option value="annual">{{ t('widgets.status.annual') }}</option>
        <option value="sick">{{ t('widgets.status.sick') }}</option>
      </select>
      <input v-model="form.start_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.end_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.reason" :placeholder="t('common.description')" class="w-40 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('leave.create') }}</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-6">
      <DataTable screen-key="leave-requests" :columns="columns" :rows="hrPayroll.leaveRequests">
        <template #status="{ row }">{{ statusLabels[row.status] }}</template>
        <template #actions="{ row }">
          <template v-if="row.status === 'pending'">
            <button class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700" @click="approve(row.id)">{{ t('common.approve') }}</button>
            <button class="rounded bg-neutral-200 px-2 py-1 text-xs font-medium text-neutral-800 hover:bg-neutral-300 dark:bg-neutral-700 dark:text-neutral-100" @click="reject(row.id)">{{ t('common.reject') }}</button>
          </template>
        </template>
      </DataTable>
    </div>
  </section>
</template>
