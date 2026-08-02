<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useHrPayrollStore } from '@/modules/hr_payroll/stores/hrPayroll'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-HR-001: employee roster.
const hrPayroll = useHrPayrollStore()

onMounted(() => {
  hrPayroll.fetchEmployees()
})

const form = reactive({
  first_name: '',
  last_name: '',
  position: '',
  department: '',
  hire_date: new Date().toISOString().slice(0, 10),
  monthly_gross_salary: '',
})
const error = ref('')

async function submit() {
  error.value = ''
  if (!form.first_name.trim() || !form.last_name.trim() || !form.monthly_gross_salary) {
    error.value = 'Ad, soyad ve brüt maaş girin.'
    return
  }
  try {
    await hrPayroll.createEmployee({ ...form })
    form.first_name = ''
    form.last_name = ''
    form.position = ''
    form.department = ''
    form.monthly_gross_salary = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Çalışan oluşturulamadı.'
  }
}

const columns: ColumnDef[] = [
  { key: 'first_name', label: 'Ad', editable: true },
  { key: 'last_name', label: 'Soyad', editable: true },
  { key: 'position', label: 'Pozisyon', editable: true },
  { key: 'department', label: 'Departman', editable: true },
  { key: 'monthly_gross_salary', label: 'Brüt Maaş', type: 'number', editable: true },
  { key: 'is_active', label: 'Aktif', type: 'boolean', editable: true },
]

async function onCellEdit({ row, column, value }: { row: any; column: string; value: any }) {
  await hrPayroll.updateEmployee(row.id, { [column]: value })
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Çalışanlar</h1>

    <form class="mt-4 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <input v-model="form.first_name" placeholder="Ad" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.last_name" placeholder="Soyad" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.position" placeholder="Pozisyon" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.department" placeholder="Departman" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.hire_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.monthly_gross_salary" type="number" step="0.01" placeholder="Brüt Maaş" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Ekle</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-6">
      <DataTable screen-key="employees" :columns="columns" :rows="hrPayroll.employees" @cell-edit="onCellEdit" />
    </div>
  </section>
</template>
