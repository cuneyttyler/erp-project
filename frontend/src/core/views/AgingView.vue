<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useARAPStore } from '@/core/stores/arap'

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

    <table class="mt-4 w-full max-w-3xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Cari</th>
          <th class="py-2 pr-4">Vade</th>
          <th class="py-2 pr-4 text-right">Bakiye</th>
          <th class="py-2 pr-4">Gecikme</th>
          <th class="py-2 pr-4">Kova</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.document_id" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4">{{ row.party_name }}</td>
          <td class="py-1.5 pr-4">{{ row.due_date }}</td>
          <td class="py-1.5 pr-4 text-right">{{ row.balance_due }}</td>
          <td class="py-1.5 pr-4">{{ row.days_overdue }} gün</td>
          <td class="py-1.5 pr-4">{{ bucketLabel[row.bucket] }}</td>
        </tr>
        <tr v-if="rows.length === 0">
          <td colspan="5" class="py-4 text-center text-neutral-400">Açık kayıt yok.</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
