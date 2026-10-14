<script setup lang="ts">
import { computed, onMounted } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-INV-001/002: stock-on-hand per item/warehouse.
const inventory = useInventoryStore()
onMounted(() => inventory.fetchStockLevels())

const columns = computed<ColumnDef[]>(() => [
  { key: 'item_sku', label: t('common.sku') },
  { key: 'item_name', label: t('common.item') },
  { key: 'warehouse_code', label: t('common.warehouse') },
  { key: 'quantity_on_hand', label: t('common.quantity'), type: 'number' },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('stock.title') }}</h1>
    <PageInsights screen-key="stock-levels" :widgets="['stock_flow','top_stock_items','stock_by_warehouse']" :follow="inventory.stockLevels" />

    <div class="mt-4">
      <DataTable
        screen-key="stock-levels"
        :columns="columns"
        :rows="inventory.stockLevels"
        :row-key="(row: any) => row.item_sku + row.warehouse_code"
      />
    </div>
  </section>
</template>
