<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { useARAPStore, type DocumentLineInput } from '@/core/stores/arap'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'

// REQ-CORE-AP-001/002/REQ-CORE-ENT-001: create, send, and record payments
// against vendor bills, scoped to the current entity.
const arap = useARAPStore()
const entity = useEntityStore()

function refresh() {
  arap.fetchParties()
  arap.fetchBills()
}

onMounted(refresh)
watch(() => entity.currentEntityId, refresh)

const form = reactive({
  party: null as number | null,
  issue_date: new Date().toISOString().slice(0, 10),
  due_date: new Date().toISOString().slice(0, 10),
  memo: '',
  lines: [{ description: '', quantity: '1', unit_price: '0' } as DocumentLineInput],
})
const error = ref('')
const paymentDrafts = reactive<Record<number, { amount: string; date: string }>>({})

function addLine() {
  form.lines.push({ description: '', quantity: '1', unit_price: '0' })
}

async function submit() {
  error.value = ''
  if (form.party === null) {
    error.value = 'Bir tedarikçi seçin.'
    return
  }
  try {
    await arap.createBill(form.party, form.issue_date, form.due_date, form.memo, form.lines)
    form.memo = ''
    form.lines = [{ description: '', quantity: '1', unit_price: '0' }]
  } catch (e: any) {
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? 'Fatura oluşturulamadı.'
  }
}

function draftFor(id: number) {
  if (!paymentDrafts[id]) {
    paymentDrafts[id] = { amount: '0', date: new Date().toISOString().slice(0, 10) }
  }
  return paymentDrafts[id]
}

async function pay(id: number) {
  const draft = draftFor(id)
  await arap.payBill(id, draft.amount, draft.date)
  draft.amount = '0'
}

const statusLabels: Record<string, string> = {
  draft: 'Taslak',
  sent: 'Gönderildi',
  partially_paid: 'Kısmi Ödendi',
  paid: 'Ödendi',
  cancelled: 'İptal',
}

const columns: ColumnDef[] = [
  { key: 'party_name', label: 'Tedarikçi' },
  { key: 'due_date', label: 'Vade' },
  { key: 'total', label: 'Toplam' },
  { key: 'balance_due', label: 'Bakiye' },
  { key: 'status', label: 'Durum' },
  { key: 'actions', label: '', sortable: false, filterable: false },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Alış Faturaları</h1>

    <form class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex gap-3">
        <select v-model.number="form.party" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Tedarikçi seçin</option>
          <option v-for="p in arap.parties" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <input v-model="form.issue_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="form.due_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="form.memo" placeholder="Açıklama" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <div v-for="(line, i) in form.lines" :key="i" class="flex items-center gap-2">
        <input v-model="line.description" placeholder="Kalem açıklaması" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="line.quantity" type="number" step="0.01" placeholder="Miktar" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="line.unit_price" type="number" step="0.01" placeholder="Birim Fiyat" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="button" class="text-sm text-blue-600" @click="addLine">+ Kalem ekle</button>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button type="submit" class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
        Taslak Oluştur
      </button>
    </form>

    <div class="mt-6">
      <DataTable screen-key="bills" :columns="columns" :rows="arap.bills">
        <template #due_date="{ row }">
          <span :class="{ 'text-red-600': row.is_overdue }">{{ row.due_date }}</span>
        </template>
        <template #status="{ row }">
          {{ statusLabels[row.status] }}
        </template>
        <template #actions="{ row }">
          <button v-if="row.status === 'draft'" class="text-sm text-blue-600 hover:underline" @click="arap.sendBill(row.id)">
            Gönder
          </button>
          <div v-else-if="row.status !== 'paid' && row.status !== 'cancelled'" class="flex items-center gap-1">
            <input v-model="draftFor(row.id).amount" type="number" step="0.01" class="w-20 rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800" />
            <button class="text-xs text-blue-600 hover:underline" @click="pay(row.id)">Ödeme Kaydet</button>
          </div>
        </template>
      </DataTable>
    </div>
  </section>
</template>
