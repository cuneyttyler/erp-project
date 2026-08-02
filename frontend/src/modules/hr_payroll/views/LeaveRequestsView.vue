<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useHrPayrollStore, type LeaveType } from '@/modules/hr_payroll/stores/hrPayroll'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

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
    error.value = 'Çalışan seçin.'
    return
  }
  try {
    await hrPayroll.createLeaveRequest({ ...form, employee: form.employee })
    form.reason = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'İzin talebi oluşturulamadı.'
  }
}

async function approve(id: number) {
  try {
    await hrPayroll.approveLeaveRequest(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Onaylanamadı.'
  }
}

async function reject(id: number) {
  try {
    await hrPayroll.rejectLeaveRequest(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Reddedilemedi.'
  }
}

const statusLabels: Record<string, string> = {
  pending: 'Beklemede',
  approved: 'Onaylandı',
  rejected: 'Reddedildi',
}
const leaveTypeLabels: Record<string, string> = {
  annual: 'Yıllık İzin',
  sick: 'Rapor',
}

const columns: ColumnDef[] = [
  { key: 'employee_name', label: 'Çalışan' },
  { key: 'leave_type', label: 'Tür', formatter: (row) => leaveTypeLabels[row.leave_type] ?? row.leave_type },
  { key: 'start_date', label: 'Başlangıç' },
  { key: 'end_date', label: 'Bitiş' },
  { key: 'days', label: 'Gün', type: 'number' },
  { key: 'status', label: 'Durum' },
  { key: 'actions', label: '', sortable: false, filterable: false },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">İzin Talepleri</h1>

    <form class="mt-4 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <select v-model.number="form.employee" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
        <option :value="null" disabled>Çalışan seçin</option>
        <option v-for="e in hrPayroll.employees" :key="e.id" :value="e.id">{{ e.first_name }} {{ e.last_name }}</option>
      </select>
      <select v-model="form.leave_type" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
        <option value="annual">Yıllık İzin</option>
        <option value="sick">Rapor</option>
      </select>
      <input v-model="form.start_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.end_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.reason" placeholder="Açıklama" class="w-40 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Talep Oluştur</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-6">
      <DataTable screen-key="leave-requests" :columns="columns" :rows="hrPayroll.leaveRequests">
        <template #status="{ row }">{{ statusLabels[row.status] }}</template>
        <template #actions="{ row }">
          <template v-if="row.status === 'pending'">
            <button class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700" @click="approve(row.id)">Onayla</button>
            <button class="rounded bg-neutral-200 px-2 py-1 text-xs font-medium text-neutral-800 hover:bg-neutral-300 dark:bg-neutral-700 dark:text-neutral-100" @click="reject(row.id)">Reddet</button>
          </template>
        </template>
      </DataTable>
    </div>
  </section>
</template>
