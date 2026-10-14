<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useLedgerStore } from '@/core/stores/ledger'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-CORE-GL-006/REQ-CORE-ENT-001/002. Deliberately a dumb table over the
// backend's deterministic aggregation query (views.TrialBalanceView) -- no
// client-side computation of the totals themselves, consistent with
// technical.md §8's "AI/UI never free-computes a financial figure" rule
// applied to plain UI code too. The consolidated toggle is independent of
// the header's "current entity" switcher -- it asks the backend for the
// cross-entity summed view (intercompany accounts excluded server-side)
// rather than any one entity's own books.
const ledger = useLedgerStore()
const entity = useEntityStore()

function refresh() {
  if (entity.currentEntityId === null) return
  ledger.fetchTrialBalance(entity.currentEntityId)
}

onMounted(refresh)
watch(() => entity.currentEntityId, refresh)

function showConsolidated() {
  ledger.fetchTrialBalance('consolidated')
}

const columns = computed<ColumnDef[]>(() => [
  { key: 'code', label: t('common.code') },
  { key: 'name', label: t('common.accountName') },
  { key: 'total_debit', label: t('common.debit') },
  { key: 'total_credit', label: t('common.credit') },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('trialBalance.title') }}</h1>
    <p class="mt-1 text-sm text-neutral-500">{{ t('trialBalance.subtitle') }}</p>
    <PageInsights screen-key="trial-balance" :widgets="['balances_by_type','revenue_expense_trend','expense_breakdown']" :follow="ledger.trialBalance" />

    <div class="mt-3 flex gap-2">
      <button
        class="rounded border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        @click="refresh"
      >
        {{ t('trialBalance.current') }}
      </button>
      <button
        v-if="entity.entities.length > 1"
        class="rounded border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        @click="showConsolidated"
      >
        {{ t('trialBalance.consolidated') }}
      </button>
    </div>

    <div class="mt-4">
      <DataTable screen-key="trial-balance" :columns="columns" :rows="ledger.trialBalance" row-key="code" />
    </div>
  </section>
</template>
