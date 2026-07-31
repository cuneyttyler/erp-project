<script setup lang="ts">
import { onMounted } from 'vue'

import { useInventoryStore } from '@/modules/inventory/stores/inventory'

// REQ-INV-001/002: stock-on-hand per item/warehouse.
const inventory = useInventoryStore()
onMounted(() => inventory.fetchStockLevels())
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Stok Durumu</h1>

    <table class="mt-4 w-full max-w-2xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">SKU</th>
          <th class="py-2 pr-4">Ürün</th>
          <th class="py-2 pr-4">Depo</th>
          <th class="py-2 pr-4 text-right">Miktar</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in inventory.stockLevels" :key="row.item_sku + row.warehouse_code" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4 font-mono">{{ row.item_sku }}</td>
          <td class="py-1.5 pr-4">{{ row.item_name }}</td>
          <td class="py-1.5 pr-4">{{ row.warehouse_code }}</td>
          <td class="py-1.5 pr-4 text-right">{{ row.quantity_on_hand }}</td>
        </tr>
        <tr v-if="inventory.stockLevels.length === 0">
          <td colspan="4" class="py-4 text-center text-neutral-400">Stokta bir hareket yok.</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
