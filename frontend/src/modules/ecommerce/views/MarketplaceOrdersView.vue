<script setup lang="ts">
import { computed, onMounted } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useEcommerceStore } from '@/modules/ecommerce/stores/ecommerce'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-ECOM-001: every order sync() has produced or attempted -- a failed
// row (e.g. an unmapped SKU) needs a human to notice and fix the listing,
// not silently disappear.
const ecommerce = useEcommerceStore()

onMounted(() => {
  ecommerce.fetchOrders()
})

const statusLabels = computed<Record<string, string>>(() => ({ new: t('marketplaceOrders.status.new'), synced: t('marketplaceOrders.status.synced'), failed: t('marketplaceOrders.status.failed') }))

const columns = computed<ColumnDef[]>(() => [
  { key: 'account_name', label: t('marketplace.connection') },
  { key: 'external_order_id', label: t('marketplaceOrders.orderNo') },
  { key: 'status', label: t('common.status') },
  { key: 'sales_order', label: t('marketplaceOrders.salesOrder') },
  { key: 'error', label: t('common.error') },
  { key: 'created_at', label: t('common.createdAt') },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('marketplaceOrders.title') }}</h1>
    <PageInsights screen-key="marketplace-orders" :widgets="['marketplace_orders_trend','marketplace_orders_by_account']" :follow="ecommerce.orders" />

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
