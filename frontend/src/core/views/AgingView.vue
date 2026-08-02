<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useARAPStore } from '@/core/stores/arap'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-CORE-AR-003/REQ-CORE-AP-002: AR/AP aging, bucketed by days overdue.
const arap = useARAPStore()
const tab = ref<'ar' | 'ap'>('ar')

onMounted(() => {
  arap.fetchARAging()
  arap.fetchAPAging()
})

const rows = computed(() => (tab.value === 'ar' ? arap.arAging : arap.apAging))
const bucketLabel: Record<string, string> = {
  current: 'Vadesi Gelmemiş',
  '1-30': '1-30 gün',
  '31-60': '31-60 gün',
  '61-90': '61-90 gün',
  '90+': '90+ gün',
}

const columns: ColumnDef[] = [
  { key: 'party_name', label: 'Cari' },
  { key: 'due_date', label: 'Vade' },
  { key: 'balance_due', label: 'Bakiye' },
  { key: 'days_overdue', label: 'Gecikme', type: 'number' },
  { key: 'bucket', label: 'Kova', formatter: (row) => bucketLabel[row.bucket] ?? row.bucket },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Yaşlandırma Raporu</h1>

    <div class="mt-4 flex gap-2">
      <button
        class="rounded px-3 py-1.5 text-sm"
        :class="tab === 'ar' ? 'bg-blue-600 text-white' : 'border border-neutral-300 dark:border-neutral-700'"
        @click="tab = 'ar'"
      >
        Alacaklar (AR)
      </button>
      <button
        class="rounded px-3 py-1.5 text-sm"
        :class="tab === 'ap' ? 'bg-blue-600 text-white' : 'border border-neutral-300 dark:border-neutral-700'"
        @click="tab = 'ap'"
      >
        Borçlar (AP)
      </button>
    </div>

    <div class="mt-4">
      <DataTable :key="tab" :screen-key="`aging-${tab}`" :columns="columns" :rows="rows" row-key="document_id" />
    </div>
  </section>
</template>
