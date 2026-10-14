<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useCatalogStore } from '@/core/stores/catalog'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-INV-001: shared product/service catalog (Core, not package-specific --
// referenced by Purchasing/Inventory/eventually Sales regardless of which
// packages a tenant has purchased).
// REQ-CORE-UX-001..004: reference DataTable integration (docs/feedback.md
// "Feedback 1") -- column reorder/hide/resize, sort/filter, inline editing,
// and personal/shared saved views, all provided by DataTable.vue itself;
// this view only declares the columns and handles persistence on edit.
const catalog = useCatalogStore()
onMounted(() => catalog.fetchItems())

const form = reactive({ sku: '', name: '', unit_of_measure: 'adet' })

async function submit() {
  if (!form.sku.trim() || !form.name.trim()) return
  await catalog.createItem({ ...form })
  form.sku = ''
  form.name = ''
}

const columns = computed<ColumnDef[]>(() => [
  { key: 'sku', label: t('common.sku'), editable: true },
  { key: 'name', label: t('common.name'), editable: true },
  { key: 'unit_of_measure', label: t('common.unit'), editable: true },
  {
    key: 'cost_method',
    label: t('items.costMethod'),
    editable: true,
    type: 'select',
    options: [
      { value: 'fifo', label: t('items.fifo') },
      { value: 'weighted_average', label: t('items.weightedAverage') },
    ],
  },
  { key: 'is_active', label: t('common.active'), editable: true, type: 'boolean' },
])

async function onCellEdit({ row, column, value }: { row: any; column: string; value: any }) {
  await catalog.updateItem(row.id, { [column]: value })
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('items.title') }}</h1>
    <PageInsights screen-key="items" :widgets="['top_moving_items','top_stock_items']" :follow="catalog.items" />

    <form class="mt-4 flex max-w-xl items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.sku') }}</label>
        <input v-model="form.sku" required class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.name') }}</label>
        <input v-model="form.name" required class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.unit') }}</label>
        <input v-model="form.unit_of_measure" class="w-20 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('common.add') }}</button>
    </form>

    <div class="mt-6">
      <DataTable screen-key="items" :columns="columns" :rows="catalog.items" @cell-edit="onCellEdit" />
    </div>
  </section>
</template>
