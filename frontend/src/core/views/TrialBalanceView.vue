<script setup lang="ts">
import { onMounted } from 'vue'

import { useLedgerStore } from '@/core/stores/ledger'

// REQ-CORE-GL-006. Deliberately a dumb table over the backend's deterministic
// aggregation query (views.TrialBalanceView) -- no client-side computation of
// the totals themselves, consistent with technical.md §8's "AI/UI never
// free-computes a financial figure" rule applied to plain UI code too.
const ledger = useLedgerStore()
onMounted(() => ledger.fetchTrialBalance())
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Mizan (Trial Balance)</h1>
    <p class="mt-1 text-sm text-neutral-500">Yalnızca kaydedilmiş (posted) yevmiye kayıtlarını içerir.</p>

    <table class="mt-4 w-full max-w-3xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Kod</th>
          <th class="py-2 pr-4">Hesap Adı</th>
          <th class="py-2 pr-4 text-right">Borç</th>
          <th class="py-2 pr-4 text-right">Alacak</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in ledger.trialBalance" :key="row.code" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4 font-mono">{{ row.code }}</td>
          <td class="py-1.5 pr-4">{{ row.name }}</td>
          <td class="py-1.5 pr-4 text-right">{{ row.total_debit }}</td>
          <td class="py-1.5 pr-4 text-right">{{ row.total_credit }}</td>
        </tr>
        <tr v-if="ledger.trialBalance.length === 0">
          <td colspan="4" class="py-4 text-center text-neutral-400">Henüz kaydedilmiş bir işlem yok.</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
