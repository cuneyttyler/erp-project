<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useCatalogStore } from '@/core/stores/catalog'
import { useEntityStore } from '@/shared/stores/entity'
import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import { useEcommerceStore, type Platform, type SyncResult } from '@/modules/ecommerce/stores/ecommerce'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-ECOM-001/003: connect a marketplace account, map its SKUs to our
// Items (MarketplaceListing), then sync orders in and push stock back out.
const ecommerce = useEcommerceStore()
const entity = useEntityStore()
const inventory = useInventoryStore()
const catalog = useCatalogStore()

onMounted(() => {
  ecommerce.fetchAccounts()
  ecommerce.fetchListings()
  entity.fetchEntities()
  inventory.fetchWarehouses()
  catalog.fetchItems()
})

const accountForm = reactive({
  platform: 'shopify' as Platform,
  name: '',
  entity: null as number | null,
  warehouse: null as number | null,
  shop_domain: '',
  api_key: '',
  api_secret: '',
})
const error = ref('')

async function createAccount() {
  error.value = ''
  if (accountForm.entity === null || accountForm.warehouse === null || !accountForm.name.trim()) {
    error.value = t('marketplace.errors.required')
    return
  }
  try {
    await ecommerce.createAccount({ ...accountForm, entity: accountForm.entity, warehouse: accountForm.warehouse })
    accountForm.name = ''
    accountForm.shop_domain = ''
    accountForm.api_key = ''
    accountForm.api_secret = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('marketplace.errors.create')
  }
}

const syncResults = reactive<Record<number, SyncResult>>({})
const syncing = reactive<Record<number, boolean>>({})

async function syncOrders(accountId: number) {
  syncing[accountId] = true
  error.value = ''
  try {
    syncResults[accountId] = await ecommerce.syncOrders(accountId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('marketplace.errors.sync')
  } finally {
    syncing[accountId] = false
  }
}

async function pushStock(accountId: number) {
  syncing[accountId] = true
  error.value = ''
  try {
    syncResults[accountId] = await ecommerce.pushStock(accountId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('marketplace.errors.push')
  } finally {
    syncing[accountId] = false
  }
}

const listingForm = reactive({ account: null as number | null, item: null as number | null, external_sku: '', external_variant_id: '', external_location_id: '' })
async function createListing() {
  if (listingForm.account === null || listingForm.item === null || !listingForm.external_sku.trim()) return
  await ecommerce.createListing({ ...listingForm, account: listingForm.account, item: listingForm.item })
  listingForm.external_sku = ''
  listingForm.external_variant_id = ''
  listingForm.external_location_id = ''
}

const platformLabels: Record<Platform, string> = { shopify: 'Shopify', trendyol: 'Trendyol', hepsiburada: 'Hepsiburada' }

const accountColumns = computed<ColumnDef[]>(() => [
  { key: 'name', label: t('common.name') },
  { key: 'platform', label: t('common.platform') },
  { key: 'entity_code', label: t('common.company') },
  { key: 'warehouse_code', label: t('common.warehouse') },
  { key: 'is_active', label: t('common.active'), type: 'boolean' },
  { key: 'last_synced_at', label: t('marketplace.lastSync') },
  { key: 'actions', label: '', sortable: false, filterable: false },
])

const listingColumns = computed<ColumnDef[]>(() => [
  { key: 'item_sku', label: t('common.item') },
  { key: 'external_sku', label: t('marketplace.externalSku') },
  { key: 'is_active', label: t('common.active'), type: 'boolean' },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('marketplace.title') }}</h1>
    <p class="mt-1 text-sm text-neutral-500">
      {{ t('marketplace.subtitle') }}
    </p>
    <PageInsights screen-key="marketplace-accounts" :widgets="['marketplace_orders_by_account','marketplace_orders_trend']" :follow="ecommerce.accounts" />

    <h2 class="mt-6 text-sm font-semibold text-neutral-700 dark:text-neutral-300">{{ t('marketplace.connections') }}</h2>
    <form class="mt-2 flex max-w-4xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="createAccount">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.platform') }}</label>
        <select v-model="accountForm.platform" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option value="shopify">Shopify</option>
          <option value="trendyol">Trendyol</option>
          <option value="hepsiburada">Hepsiburada</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.name') }}</label>
        <input v-model="accountForm.name" class="w-40 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.company') }}</label>
        <select v-model.number="accountForm.entity" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.select') }}</option>
          <option v-for="e in entity.entities" :key="e.id" :value="e.id">{{ e.code }} — {{ e.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.warehouse') }}</label>
        <select v-model.number="accountForm.warehouse" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.select') }}</option>
          <option v-for="w in inventory.warehouses" :key="w.id" :value="w.id">{{ w.code }} — {{ w.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.shopDomain') }}</label>
        <input v-model="accountForm.shop_domain" placeholder="my-shop.myshopify.com" class="w-48 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.apiKey') }}</label>
        <input v-model="accountForm.api_key" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.apiSecret') }}</label>
        <input v-model="accountForm.api_secret" type="password" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('marketplace.connect') }}</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-3">
      <DataTable screen-key="ecommerce-accounts" :columns="accountColumns" :rows="ecommerce.accounts">
        <template #platform="{ row }">{{ platformLabels[row.platform as keyof typeof platformLabels] }}</template>
        <template #actions="{ row }">
          <div class="flex items-center gap-1">
            <button :disabled="syncing[row.id]" class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50" @click="syncOrders(row.id)">
              {{ t('marketplace.fetchOrders') }}
            </button>
            <button :disabled="syncing[row.id]" class="rounded bg-neutral-800 px-2 py-1 text-xs font-medium text-white hover:bg-neutral-900 disabled:opacity-50" @click="pushStock(row.id)">
              {{ t('marketplace.pushStock') }}
            </button>
          </div>
          <p v-if="syncResults[row.id]" class="mt-1 text-xs text-neutral-500">
            <span v-if="syncResults[row.id].created !== undefined">{{ t('marketplace.result.fetched', { created: syncResults[row.id].created, skipped: syncResults[row.id].skipped }) }} </span>
            <span v-if="syncResults[row.id].pushed !== undefined">{{ t('marketplace.result.pushed', { n: syncResults[row.id].pushed }) }} </span>
            {{ t('marketplace.result.failed', { n: syncResults[row.id].failed }) }}
          </p>
        </template>
      </DataTable>
    </div>

    <h2 class="mt-8 text-sm font-semibold text-neutral-700 dark:text-neutral-300">{{ t('marketplace.listings') }}</h2>
    <form class="mt-2 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="createListing">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.connection') }}</label>
        <select v-model.number="listingForm.account" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.select') }}</option>
          <option v-for="a in ecommerce.accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.item') }}</label>
        <select v-model.number="listingForm.item" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.select') }}</option>
          <option v-for="i in catalog.items" :key="i.id" :value="i.id">{{ i.sku }} — {{ i.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.externalSku') }}</label>
        <input v-model="listingForm.external_sku" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.variantId') }}</label>
        <input v-model="listingForm.external_variant_id" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('marketplace.locationId') }}</label>
        <input v-model="listingForm.external_location_id" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('marketplace.map') }}</button>
    </form>
    <div class="mt-3">
      <DataTable screen-key="ecommerce-listings" :columns="listingColumns" :rows="ecommerce.listings" />
    </div>
  </section>
</template>
