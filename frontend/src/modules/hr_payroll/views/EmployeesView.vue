<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useHrPayrollStore } from '@/modules/hr_payroll/stores/hrPayroll'

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

    <div class="mt-6 max-w-3xl space-y-2">
      <div v-for="e in hrPayroll.employees" :key="e.id" class="flex items-center justify-between rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
        <div>
          <span class="font-medium text-neutral-900 dark:text-neutral-100">{{ e.first_name }} {{ e.last_name }}</span>
          <span class="ml-2 text-neutral-500">{{ e.position }} · {{ e.department }}</span>
        </div>
        <span class="text-neutral-500">{{ e.monthly_gross_salary }} TRY/ay</span>
      </div>
    </div>
  </section>
</template>
