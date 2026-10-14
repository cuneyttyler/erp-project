<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useCatalogStore } from '@/core/stores/catalog'
import { useARAPStore } from '@/core/stores/arap'
import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import { usePurchasingStore, type POLineInput } from '@/modules/purchasing/stores/purchasing'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-PUR-001/002/005: create, approve, send, and receive purchase orders.
const purchasing = usePurchasingStore()
const arap = useARAPStore()
const inventory = useInventoryStore()
const catalog = useCatalogStore()

onMounted(() => {
  purchasing.fetchOrders()
  arap.fetchParties()
  inventory.fetchWarehouses()
  catalog.fetchItems()
})

const form = reactive({
  party: null as number | null,
  warehouse: null as number | null,
  order_date: new Date().toISOString().slice(0, 10),
  lines: [{ item: null as number | null, quantity_ordered: '1', unit_price: '0' }],
})
const error = ref('')
// per-order draft of "quantity to receive now", keyed by line id
const receiveDrafts = reactive<Record<number, string>>({})

function addLine() {
  form.lines.push({ item: null, quantity_ordered: '1', unit_price: '0' })
}

async function submit() {
  error.value = ''
  if (form.party === null || form.warehouse === null) {
    error.value = t('purchaseOrders.errors.required')
    return
  }
  try {
    const lines: POLineInput[] = form.lines
      .filter((l) => l.item !== null)
      .map((l) => ({ item: l.item as number, quantity_ordered: l.quantity_ordered, unit_price: l.unit_price }))
    await purchasing.createOrder(form.party, form.warehouse, form.order_date, lines)
    form.lines = [{ item: null, quantity_ordered: '1', unit_price: '0' }]
  } catch (e: any) {
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? t('purchaseOrders.errors.create')
  }
}

async function approve(id: number) {
  try {
    await purchasing.approveOrder(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('purchaseOrders.errors.approve')
  }
}

async function send(id: number) {
  try {
    await purchasing.sendOrder(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('purchaseOrders.errors.send')
  }
}

async function receive(orderId: number, lineIds: number[]) {
  const lines = lineIds
    .map((lineId) => ({ line_id: lineId, quantity: receiveDrafts[lineId] || '0' }))
    .filter((l) => parseFloat(l.quantity) > 0)
  if (lines.length === 0) return
  try {
    await purchasing.receiveOrder(orderId, lines)
    lineIds.forEach((id) => (receiveDrafts[id] = ''))
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('purchaseOrders.errors.receive')
  }
}

const statusLabels = computed<Record<string, string>>(() => ({
  draft: t('widgets.status.draft'),
  sent: t('widgets.status.sent'),
  partially_received: t('widgets.status.partially_received'),
  received: t('widgets.status.received'),
  cancelled: t('widgets.status.cancelled'),
}))
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('purchaseOrders.title') }}</h1>
    <PageInsights screen-key="purchase-orders" :widgets="['purchase_trend','purchase_orders_by_status','top_vendors']" :follow="purchasing.orders" />

    <form class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex flex-wrap gap-3">
        <select v-model.number="form.party" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.selectVendor') }}</option>
          <option v-for="p in arap.parties" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <select v-model.number="form.warehouse" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.selectWarehouse') }}</option>
          <option v-for="w in inventory.warehouses" :key="w.id" :value="w.id">{{ w.code }} — {{ w.name }}</option>
        </select>
        <input v-model="form.order_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <div v-for="(line, i) in form.lines" :key="i" class="flex items-center gap-2">
        <select v-model.number="line.item" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('common.selectItem') }}</option>
          <option v-for="it in catalog.items" :key="it.id" :value="it.id">{{ it.sku }} — {{ it.name }}</option>
        </select>
        <input v-model="line.quantity_ordered" type="number" step="0.01" :placeholder="t('common.quantity')" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="line.unit_price" type="number" step="0.01" :placeholder="t('common.unitPrice')" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="button" class="block text-sm text-blue-600 hover:underline" @click="addLine">{{ t('common.addLine') }}</button>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button type="submit" class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
        {{ t('common.createDraft') }}
      </button>
    </form>

    <div class="mt-6 max-w-4xl space-y-4">
      <div v-for="order in purchasing.orders" :key="order.id" class="rounded border border-neutral-200 p-4 dark:border-neutral-800">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-neutral-900 dark:text-neutral-100">PO-{{ order.id }} — {{ order.party_name }}</span>
            <span class="ml-2 text-sm text-neutral-500">{{ order.warehouse_code }} · {{ t('common.total') }} {{ order.total }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm">{{ statusLabels[order.status] }}</span>
            <button
              v-if="order.status === 'draft' && order.requires_approval && !order.approved_at"
              class="rounded bg-amber-500 px-2 py-1 text-xs font-medium text-white hover:bg-amber-600"
              @click="approve(order.id)"
            >
              {{ t('purchaseOrders.approveOver', { n: '10.000' }) }}
            </button>
            <button
              v-if="order.status === 'draft'"
              class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              @click="send(order.id)"
            >
              {{ t('common.send') }}
            </button>
          </div>
        </div>

        <table v-if="order.status !== 'draft' && order.status !== 'cancelled'" class="mt-3 w-full text-left text-xs">
          <thead>
            <tr class="text-neutral-500">
              <th class="py-1 pr-3">{{ t('common.item') }}</th>
              <th class="py-1 pr-3 text-right">{{ t('common.ordered') }}</th>
              <th class="py-1 pr-3 text-right">{{ t('purchaseOrders.received') }}</th>
              <th class="py-1 pr-3 text-right">{{ t('common.remaining') }}</th>
              <th class="py-1 pr-3" v-if="order.status !== 'received'">{{ t('purchaseOrders.receiveNow') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="line in order.lines" :key="line.id">
              <td class="py-1 pr-3">{{ line.item_sku }}</td>
              <td class="py-1 pr-3 text-right">{{ line.quantity_ordered }}</td>
              <td class="py-1 pr-3 text-right">{{ line.quantity_received }}</td>
              <td class="py-1 pr-3 text-right">{{ line.quantity_remaining }}</td>
              <td class="py-1 pr-3" v-if="order.status !== 'received'">
                <input
                  v-model="receiveDrafts[line.id]"
                  type="number"
                  step="0.01"
                  class="w-20 rounded border border-neutral-300 px-1 py-0.5 dark:border-neutral-700 dark:bg-neutral-800"
                />
              </td>
            </tr>
          </tbody>
        </table>
        <button
          v-if="order.status === 'sent' || order.status === 'partially_received'"
          class="mt-2 text-xs text-blue-600 hover:underline"
          @click="receive(order.id, order.lines.map((l) => l.id))"
        >
          {{ t('purchaseOrders.receive') }}
        </button>
      </div>
    </div>
  </section>
</template>
