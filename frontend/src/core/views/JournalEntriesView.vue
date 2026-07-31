<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { useLedgerStore, type JournalLineInput } from '@/core/stores/ledger'

// REQ-CORE-GL-002: create + post journal entries. Posting is a deliberate
// separate step from creation (ledger.postEntry), matching the backend's
// draft -> posted workflow -- nothing here lets you edit a posted entry.
const ledger = useLedgerStore()

onMounted(() => {
  ledger.fetchAccounts()
  ledger.fetchEntries()
})

const form = reactive({
  date: new Date().toISOString().slice(0, 10),
  memo: '',
  lines: [
    { account: null as number | null, debit: '0', credit: '0', description: '' },
    { account: null as number | null, debit: '0', credit: '0', description: '' },
  ],
})
const error = ref('')
const submitting = ref(false)

const totalDebit = computed(() =>
  form.lines.reduce((sum, l) => sum + (parseFloat(l.debit) || 0), 0),
)
const totalCredit = computed(() =>
  form.lines.reduce((sum, l) => sum + (parseFloat(l.credit) || 0), 0),
)
const isBalanced = computed(
  () => totalDebit.value === totalCredit.value && totalDebit.value > 0,
)

function addLine() {
  form.lines.push({ account: null, debit: '0', credit: '0', description: '' })
}

async function submit() {
  error.value = ''
  if (!isBalanced.value) {
    error.value = 'Borç ve alacak toplamları eşit olmalı (ve sıfırdan büyük).'
    return
  }
  submitting.value = true
  try {
    const lines: JournalLineInput[] = form.lines
      .filter((l) => l.account !== null)
      .map((l) => ({ account: l.account as number, debit: l.debit, credit: l.credit, description: l.description }))
    await ledger.createEntry(form.date, form.memo, lines)
    form.memo = ''
    form.lines = [
      { account: null, debit: '0', credit: '0', description: '' },
      { account: null, debit: '0', credit: '0', description: '' },
    ]
  } catch (e: any) {
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? 'Kayıt oluşturulamadı.'
  } finally {
    submitting.value = false
  }
}

async function post(id: number) {
  await ledger.postEntry(id)
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Yevmiye Kayıtları</h1>

    <form
      class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800"
      @submit.prevent="submit"
    >
      <div class="flex gap-3">
        <input v-model="form.date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="form.memo" placeholder="Açıklama" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <div v-for="(line, i) in form.lines" :key="i" class="flex items-center gap-2">
        <select v-model.number="line.account" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Hesap seçin</option>
          <option v-for="a in ledger.accounts" :key="a.id" :value="a.id">{{ a.code }} — {{ a.name }}</option>
        </select>
        <input v-model="line.debit" type="number" step="0.01" placeholder="Borç" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="line.credit" type="number" step="0.01" placeholder="Alacak" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <button type="button" class="text-sm text-blue-600" @click="addLine">+ Satır ekle</button>

      <p class="text-xs text-neutral-500">
        Toplam Borç: {{ totalDebit.toFixed(2) }} · Toplam Alacak: {{ totalCredit.toFixed(2) }}
        <span v-if="isBalanced" class="text-emerald-600">✓ dengeli</span>
      </p>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button
        type="submit"
        :disabled="submitting"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        Taslak Oluştur
      </button>
    </form>

    <table class="mt-6 w-full max-w-3xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Tarih</th>
          <th class="py-2 pr-4">Açıklama</th>
          <th class="py-2 pr-4">Durum</th>
          <th class="py-2 pr-4"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in ledger.entries" :key="entry.id" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4">{{ entry.date }}</td>
          <td class="py-1.5 pr-4">{{ entry.memo }}</td>
          <td class="py-1.5 pr-4">
            <span :class="entry.status === 'posted' ? 'text-emerald-600' : 'text-amber-600'">
              {{ entry.status === 'posted' ? 'Kayıtlı' : 'Taslak' }}
            </span>
          </td>
          <td class="py-1.5 pr-4">
            <button
              v-if="entry.status === 'draft'"
              class="text-sm text-blue-600 hover:underline"
              @click="post(entry.id)"
            >
              Kaydet (Post)
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
