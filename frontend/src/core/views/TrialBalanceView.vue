<script setup lang="ts">
import { onMounted } from 'vue'

import { useLedgerStore } from '@/core/stores/ledger'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-CORE-GL-006. Deliberately a dumb table over the backend's deterministic
// aggregation query (views.TrialBalanceView) -- no client-side computation of
// the totals themselves, consistent with technical.md §8's "AI/UI never
// free-computes a financial figure" rule applied to plain UI code too.
const ledger = useLedgerStore()
onMounted(() => ledger.fetchTrialBalance())

const columns: ColumnDef[] = [
  { key: 'code', label: 'Kod' },
  { key: 'name', label: 'Hesap Adı' },
  { key: 'total_debit', label: 'Borç' },
  { key: 'total_credit', label: 'Alacak' },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Mizan (Trial Balance)</h1>
    <p class="mt-1 text-sm text-neutral-500">Yalnızca kaydedilmiş (posted) yevmiye kayıtlarını içerir.</p>

    <div class="mt-4">
      <DataTable screen-key="trial-balance" :columns="columns" :rows="ledger.trialBalance" row-key="code" />
    </div>
  </section>
</template>
