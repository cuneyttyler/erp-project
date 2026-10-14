<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useARAPStore } from '@/core/stores/arap'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-CORE-AR-003/REQ-CORE-AP-002/REQ-CORE-ENT-001: AR/AP aging, bucketed
// by days overdue, scoped to the current entity.
const arap = useARAPStore()
const entityStore = useEntityStore()
const tab = ref<'ar' | 'ap'>('ar')

function refresh() {
  arap.fetchARAging()
  arap.fetchAPAging()
}

onMounted(refresh)
watch(() => entityStore.currentEntityId, refresh)

const rows = computed(() => (tab.value === 'ar' ? arap.arAging : arap.apAging))
const bucketKey: Record<string, string> = {
  current: 'aging.current',
  '1-30': 'aging.d1_30',
  '31-60': 'aging.d31_60',
  '61-90': 'aging.d61_90',
  '90+': 'aging.d90',
}

const columns = computed<ColumnDef[]>(() => [
  { key: 'party_name', label: t('aging.party') },
  { key: 'due_date', label: t('common.dueDate') },
  { key: 'balance_due', label: t('common.balance') },
  { key: 'days_overdue', label: t('aging.daysOverdue'), type: 'number' },
  { key: 'bucket', label: t('aging.bucket'), formatter: (row) => (bucketKey[row.bucket] ? t(bucketKey[row.bucket]) : row.bucket) },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('aging.title') }}</h1>
    <PageInsights screen-key="aging" :widgets="['ar_aging','ap_aging','cash_forecast']" />

    <div class="mt-4 flex gap-2">
      <button
        class="rounded px-3 py-1.5 text-sm"
        :class="tab === 'ar' ? 'bg-blue-600 text-white' : 'border border-neutral-300 dark:border-neutral-700'"
        @click="tab = 'ar'"
      >
        {{ t('aging.receivables') }}
      </button>
      <button
        class="rounded px-3 py-1.5 text-sm"
        :class="tab === 'ap' ? 'bg-blue-600 text-white' : 'border border-neutral-300 dark:border-neutral-700'"
        @click="tab = 'ap'"
      >
        {{ t('aging.payables') }}
      </button>
    </div>

    <div class="mt-4">
      <DataTable :key="tab" :screen-key="`aging-${tab}`" :columns="columns" :rows="rows" row-key="document_id" />
    </div>
  </section>
</template>
