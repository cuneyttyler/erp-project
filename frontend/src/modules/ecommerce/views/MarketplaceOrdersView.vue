<script setup lang="ts">
import { onMounted } from 'vue'

import { useEcommerceStore } from '@/modules/ecommerce/stores/ecommerce'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-ECOM-001: every order sync() has produced or attempted -- a failed
// row (e.g. an unmapped SKU) needs a human to notice and fix the listing,
// not silently disappear.
const ecommerce = useEcommerceStore()

onMounted(() => {
  ecommerce.fetchOrders()
})

const statusLabels: Record<string, string> = { new: 'Yeni', synced: 'Senkronize', failed: 'Başarısız' }

const columns: ColumnDef[] = [
  { key: 'account_name', label: 'Bağlantı' },
  { key: 'external_order_id', label: 'Sipariş No' },
  { key: 'status', label: 'Durum' },
  { key: 'sales_order', label: 'Satış Siparişi' },
  { key: 'error', label: 'Hata' },
  { key: 'created_at', label: 'Oluşturulma' },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Pazaryeri Siparişleri</h1>

    <div class="mt-4">
      <DataTable screen-key="ecommerce-orders" :columns="columns" :rows="ecommerce.orders">
        <template #status="{ row }">{{ statusLabels[row.status] }}</template>
        <template #sales_order="{ row }">
          <RouterLink v-if="row.sales_order" to="/sales-orders" class="text-blue-600 underline dark:text-blue-400">#{{ row.sales_order }}</RouterLink>
          <span v-else>—</span>
        </template>
      </DataTable>
    </div>
  </section>
</template>
