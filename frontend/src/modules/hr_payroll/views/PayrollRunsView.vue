<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useHrPayrollStore } from '@/modules/hr_payroll/stores/hrPayroll'

// REQ-HR-003: payroll run gross-to-net calculation.
const hrPayroll = useHrPayrollStore()

onMounted(() => {
  hrPayroll.fetchPayrollRuns()
})

const now = new Date()
const form = reactive({
  period_year: now.getFullYear(),
  period_month: now.getMonth() + 1,
})
const error = ref('')
const expanded = reactive<Record<number, boolean>>({})

async function submit() {
  error.value = ''
  try {
    await hrPayroll.createPayrollRun(form.period_year, form.period_month)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Bordro dönemi oluşturulamadı.'
  }
}

async function calculate(id: number) {
  try {
    await hrPayroll.calculatePayrollRun(id)
    expanded[id] = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Hesaplanamadı.'
  }
}

async function finalize(id: number) {
  try {
    await hrPayroll.finalizePayrollRun(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Kesinleştirilemedi.'
  }
}

const statusLabels: Record<string, string> = {
  draft: 'Taslak',
  finalized: 'Kesinleşti',
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Bordro Dönemleri</h1>

    <form class="mt-4 flex max-w-md items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <input v-model.number="form.period_year" type="number" placeholder="Yıl" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model.number="form.period_month" type="number" min="1" max="12" placeholder="Ay" class="w-20 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Dönem Oluştur</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-6 max-w-4xl space-y-3">
      <div v-for="run in hrPayroll.payrollRuns" :key="run.id" class="rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
        <div class="flex items-center justify-between">
          <span class="font-medium text-neutral-900 dark:text-neutral-100">{{ run.period_year }}-{{ String(run.period_month).padStart(2, '0') }}</span>
          <div class="flex items-center gap-2">
            <span>{{ statusLabels[run.status] }}</span>
            <button
              v-if="run.status === 'draft'"
              class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              @click="calculate(run.id)"
            >
              Hesapla
            </button>
            <button
              v-if="run.status === 'draft' && run.payslips.length > 0"
              class="rounded bg-neutral-200 px-2 py-1 text-xs font-medium text-neutral-800 hover:bg-neutral-300 dark:bg-neutral-700 dark:text-neutral-100"
              @click="finalize(run.id)"
            >
              Kesinleştir
            </button>
            <button
              v-if="run.payslips.length > 0"
              class="text-xs text-blue-600 hover:underline"
              @click="expanded[run.id] = !expanded[run.id]"
            >
              {{ expanded[run.id] ? 'Gizle' : `${run.payslips.length} bordro göster` }}
            </button>
          </div>
        </div>

        <table v-if="expanded[run.id]" class="mt-3 w-full text-left text-xs">
          <thead class="text-neutral-500">
            <tr>
              <th class="py-1 pr-2">Çalışan</th>
              <th class="py-1 pr-2">Brüt</th>
              <th class="py-1 pr-2">SGK</th>
              <th class="py-1 pr-2">İşsizlik</th>
              <th class="py-1 pr-2">Gelir Vergisi</th>
              <th class="py-1 pr-2">Damga Vergisi</th>
              <th class="py-1 pr-2">Net</th>
              <th class="py-1 pr-2">İşveren Toplam Maliyet</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in run.payslips" :key="p.id" class="border-t border-neutral-100 dark:border-neutral-800">
              <td class="py-1 pr-2 text-neutral-900 dark:text-neutral-100">{{ p.employee_name }}</td>
              <td class="py-1 pr-2">{{ p.gross_salary }}</td>
              <td class="py-1 pr-2">{{ p.sgk_employee_premium }}</td>
              <td class="py-1 pr-2">{{ p.unemployment_employee_premium }}</td>
              <td class="py-1 pr-2">{{ p.income_tax }}</td>
              <td class="py-1 pr-2">{{ p.stamp_duty }}</td>
              <td class="py-1 pr-2 font-medium text-neutral-900 dark:text-neutral-100">{{ p.net_salary }}</td>
              <td class="py-1 pr-2">{{ p.total_employer_cost }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
