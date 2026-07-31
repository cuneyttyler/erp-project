<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useARAPStore, type DocumentLineInput } from '@/core/stores/arap'

// REQ-CORE-AR-001/002: create, send, and record payments against customer invoices.
const arap = useARAPStore()

onMounted(() => {
  arap.fetchParties()
  arap.fetchInvoices()
})

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
    error.value = 'Bir müşteri seçin.'
    return
  }
  try {
    await arap.createInvoice(form.party, form.issue_date, form.due_date, form.memo, form.lines)
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
  await arap.payInvoice(id, draft.amount, draft.date)
  draft.amount = '0'
}

const statusLabels: Record<string, string> = {
  draft: 'Taslak',
  sent: 'Gönderildi',
  partially_paid: 'Kısmi Ödendi',
  paid: 'Ödendi',
  cancelled: 'İptal',
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Satış Faturaları</h1>

    <form class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex gap-3">
        <select v-model.number="form.party" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Müşteri seçin</option>
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

    <table class="mt-6 w-full max-w-4xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Müşteri</th>
          <th class="py-2 pr-4">Vade</th>
          <th class="py-2 pr-4 text-right">Toplam</th>
          <th class="py-2 pr-4 text-right">Bakiye</th>
          <th class="py-2 pr-4">Durum</th>
          <th class="py-2 pr-4"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in arap.invoices" :key="doc.id" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4">{{ doc.party_name }}</td>
          <td class="py-1.5 pr-4" :class="{ 'text-red-600': doc.is_overdue }">{{ doc.due_date }}</td>
          <td class="py-1.5 pr-4 text-right">{{ doc.total }}</td>
          <td class="py-1.5 pr-4 text-right">{{ doc.balance_due }}</td>
          <td class="py-1.5 pr-4">{{ statusLabels[doc.status] }}</td>
          <td class="py-1.5 pr-4">
            <button v-if="doc.status === 'draft'" class="text-sm text-blue-600 hover:underline" @click="arap.sendInvoice(doc.id)">
              Gönder
            </button>
            <div v-else-if="doc.status !== 'paid' && doc.status !== 'cancelled'" class="flex items-center gap-1">
              <input v-model="draftFor(doc.id).amount" type="number" step="0.01" class="w-20 rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800" />
              <button class="text-xs text-blue-600 hover:underline" @click="pay(doc.id)">Tahsilat Kaydet</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
