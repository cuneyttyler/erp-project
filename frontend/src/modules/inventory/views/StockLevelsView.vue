<script setup lang="ts">
import { onMounted } from 'vue'

import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-INV-001/002: stock-on-hand per item/warehouse.
const inventory = useInventoryStore()
onMounted(() => inventory.fetchStockLevels())

const columns: ColumnDef[] = [
  { key: 'item_sku', label: 'SKU' },
  { key: 'item_name', label: 'Ürün' },
  { key: 'warehouse_code', label: 'Depo' },
  { key: 'quantity_on_hand', label: 'Miktar', type: 'number' },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Stok Durumu</h1>

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
