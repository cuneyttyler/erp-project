<script setup lang="ts">
import { onMounted, reactive } from 'vue'

import { useARAPStore } from '@/core/stores/arap'
import { useSalesCrmStore } from '@/modules/sales_crm/stores/salesCrm'

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

    <div class="mt-6 max-w-3xl space-y-2">
      <div v-for="lead in salesCrm.leads" :key="lead.id" class="flex items-center justify-between rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
        <div>
          <span class="font-medium text-neutral-900 dark:text-neutral-100">{{ lead.name }}</span>
          <span class="ml-2 text-neutral-500">{{ lead.source }}</span>
          <span class="ml-2 text-neutral-500">— {{ statusLabels[lead.status] }}</span>
        </div>
        <div v-if="lead.status === 'new'" class="flex items-center gap-2">
          <button class="text-xs text-blue-600 hover:underline" @click="salesCrm.qualifyLead(lead.id)">Nitele</button>
          <button class="text-xs text-red-600 hover:underline" @click="salesCrm.loseLead(lead.id)">Kaybedildi</button>
        </div>
        <div v-else-if="lead.status === 'qualified'" class="flex items-center gap-2">
          <select v-model.number="winTargets[lead.id]" class="rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800">
            <option :value="null" disabled>Cari seçin</option>
            <option v-for="p in arap.parties" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <button
            class="text-xs text-emerald-600 hover:underline"
            @click="winTargets[lead.id] && salesCrm.winLead(lead.id, winTargets[lead.id]!)"
          >
            Kazanıldı
          </button>
          <button class="text-xs text-red-600 hover:underline" @click="salesCrm.loseLead(lead.id)">Kaybedildi</button>
        </div>
      </div>
    </div>
  </section>
</template>
