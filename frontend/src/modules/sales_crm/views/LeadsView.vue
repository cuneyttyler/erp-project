<script setup lang="ts">
import { onMounted, reactive } from 'vue'

import { useARAPStore } from '@/core/stores/arap'
import { useSalesCrmStore } from '@/modules/sales_crm/stores/salesCrm'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-CRM-001: lead pipeline (new -> qualified -> won/lost).
const salesCrm = useSalesCrmStore()
const arap = useARAPStore()

onMounted(() => {
  salesCrm.fetchLeads()
  arap.fetchParties()
})

const form = reactive({ name: '', source: '' })
const winTargets = reactive<Record<number, number | null>>({})

async function submit() {
  if (!form.name.trim()) return
  await salesCrm.createLead({ ...form })
  form.name = ''
  form.source = ''
}

const statusLabels: Record<string, string> = {
  new: 'Yeni',
  qualified: 'Nitelikli',
  won: 'Kazanıldı',
  lost: 'Kaybedildi',
}

const columns: ColumnDef[] = [
  { key: 'name', label: 'Ad / Firma', editable: true },
  { key: 'source', label: 'Kaynak', editable: true },
  { key: 'status', label: 'Durum' },
  { key: 'actions', label: '', sortable: false, filterable: false },
]

async function onCellEdit({ row, column, value }: { row: any; column: string; value: any }) {
  await salesCrm.updateLead(row.id, { [column]: value })
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Potansiyel Müşteriler</h1>

    <form class="mt-4 flex max-w-xl items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">Ad / Firma</label>
        <input v-model="form.name" required class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Kaynak</label>
        <input v-model="form.source" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Ekle</button>
    </form>

    <div class="mt-6">
      <DataTable screen-key="leads" :columns="columns" :rows="salesCrm.leads" @cell-edit="onCellEdit">
        <template #status="{ row }">{{ statusLabels[row.status] }}</template>
        <template #actions="{ row }">
          <div v-if="row.status === 'new'" class="flex items-center gap-2">
            <button class="text-xs text-blue-600 hover:underline" @click="salesCrm.qualifyLead(row.id)">Nitele</button>
            <button class="text-xs text-red-600 hover:underline" @click="salesCrm.loseLead(row.id)">Kaybedildi</button>
          </div>
          <div v-else-if="row.status === 'qualified'" class="flex items-center gap-2">
            <select v-model.number="winTargets[row.id]" class="rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800">
              <option :value="null" disabled>Cari seçin</option>
              <option v-for="p in arap.parties" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
            <button
              class="text-xs text-emerald-600 hover:underline"
              @click="winTargets[row.id] && salesCrm.winLead(row.id, winTargets[row.id]!)"
            >
              Kazanıldı
            </button>
            <button class="text-xs text-red-600 hover:underline" @click="salesCrm.loseLead(row.id)">Kaybedildi</button>
          </div>
        </template>
      </DataTable>
    </div>
  </section>
</template>
