<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useLedgerStore, type JournalLineInput } from '@/core/stores/ledger'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-CORE-GL-002/REQ-CORE-ENT-001: create + post journal entries, scoped
// to the current entity's own ledger. Posting is a deliberate separate
// step from creation (ledger.postEntry), matching the backend's draft ->
// posted workflow -- nothing here lets you edit a posted entry.
const ledger = useLedgerStore()
const entity = useEntityStore()

function refresh() {
  ledger.fetchAccounts()
  ledger.fetchEntries()
}

onMounted(refresh)
watch(() => entity.currentEntityId, refresh)

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
    error.value = t('journal.errors.unbalanced')
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
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? t('journal.errors.create')
  } finally {
    submitting.value = false
  }
}

async function post(id: number) {
  await ledger.postEntry(id)
}

const columns = computed<ColumnDef[]>(() => [
  { key: 'date', label: t('common.date') },
  { key: 'memo', label: t('common.description') },
  { key: 'status', label: t('common.status') },
  { key: 'actions', label: '', sortable: false, filterable: false },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('journal.title') }}</h1>
    <PageInsights screen-key="journal-entries" :widgets="['journal_activity','revenue_expense_trend']" :follow="ledger.entries" />

    <form
      class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800"
      @submit.prevent="submit"
    >
      <div class="flex gap-3">
        <input v-model="form.date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="form.memo" :placeholder="t('common.description')" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <div v-for="(line, i) in form.lines" :key="i" class="flex items-center gap-2">
        <select v-model.number="line.account" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.selectAccount') }}</option>
          <option v-for="a in ledger.accounts" :key="a.id" :value="a.id">{{ a.code }} — {{ a.name }}</option>
        </select>
        <input v-model="line.debit" type="number" step="0.01" :placeholder="t('common.debit')" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="line.credit" type="number" step="0.01" :placeholder="t('common.credit')" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <button type="button" class="block text-sm text-blue-600 hover:underline" @click="addLine">{{ t('journal.addRow') }}</button>

      <p class="text-xs text-neutral-500">
        {{ t('journal.totalDebit') }}: {{ totalDebit.toFixed(2) }} · {{ t('journal.totalCredit') }}: {{ totalCredit.toFixed(2) }}
        <span v-if="isBalanced" class="text-emerald-600">{{ t('journal.balanced') }}</span>
      </p>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button
        type="submit"
        :disabled="submitting"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {{ t('common.createDraft') }}
      </button>
    </form>

    <div class="mt-6">
      <DataTable screen-key="journal-entries" :columns="columns" :rows="ledger.entries">
        <template #status="{ row }">
          <span :class="row.status === 'posted' ? 'text-emerald-600' : 'text-amber-600'">
            {{ row.status === 'posted' ? t('widgets.status.posted') : t('widgets.status.draft') }}
          </span>
        </template>
        <template #actions="{ row }">
          <button v-if="row.status === 'draft'" class="text-sm text-blue-600 hover:underline" @click="post(row.id)">
            {{ t('journal.post') }}
          </button>
        </template>
      </DataTable>
    </div>
  </section>
</template>
