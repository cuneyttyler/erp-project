<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useCatalogStore } from '@/core/stores/catalog'
import { useARAPStore } from '@/core/stores/arap'
import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import { useSalesCrmStore, type SOLineInput } from '@/modules/sales_crm/stores/salesCrm'

// REQ-CRM-002/003: create, confirm, and fulfill sales orders.
const salesCrm = useSalesCrmStore()
const arap = useARAPStore()
const inventory = useInventoryStore()
const catalog = useCatalogStore()

onMounted(() => {
  salesCrm.fetchOrders()
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
const fulfillDrafts = reactive<Record<number, string>>({})

function addLine() {
  form.lines.push({ item: null, quantity_ordered: '1', unit_price: '0' })
}

async function submit() {
  error.value = ''
  if (form.party === null || form.warehouse === null) {
    error.value = 'Müşteri ve depo seçin.'
    return
  }
  try {
    const lines: SOLineInput[] = form.lines
      .filter((l) => l.item !== null)
      .map((l) => ({ item: l.item as number, quantity_ordered: l.quantity_ordered, unit_price: l.unit_price }))
    await salesCrm.createOrder(form.party, form.warehouse, form.order_date, lines)
    form.lines = [{ item: null, quantity_ordered: '1', unit_price: '0' }]
  } catch (e: any) {
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? 'Sipariş oluşturulamadı.'
  }
}

async function confirm(id: number) {
  try {
    await salesCrm.confirmOrder(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Onaylanamadı.'
  }
}

async function fulfill(orderId: number, lineIds: number[]) {
  const lines = lineIds
    .map((lineId) => ({ line_id: lineId, quantity: fulfillDrafts[lineId] || '0' }))
    .filter((l) => parseFloat(l.quantity) > 0)
  if (lines.length === 0) return
  try {
    await salesCrm.fulfillOrder(orderId, lines)
    lineIds.forEach((id) => (fulfillDrafts[id] = ''))
    error.value = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Sevkiyat başarısız.'
  }
}

const statusLabels: Record<string, string> = {
  draft: 'Taslak',
  confirmed: 'Onaylandı',
  partially_fulfilled: 'Kısmi Sevk',
  fulfilled: 'Sevk Edildi',
  cancelled: 'İptal',
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Satış Siparişleri</h1>

    <form class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex gap-3">
        <select v-model.number="form.party" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Müşteri seçin</option>
          <option v-for="p in arap.parties" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <select v-model.number="form.warehouse" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Depo seçin</option>
          <option v-for="w in inventory.warehouses" :key="w.id" :value="w.id">{{ w.code }} — {{ w.name }}</option>
        </select>
        <input v-model="form.order_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <div v-for="(line, i) in form.lines" :key="i" class="flex items-center gap-2">
        <select v-model.number="line.item" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Ürün seçin</option>
          <option v-for="it in catalog.items" :key="it.id" :value="it.id">{{ it.sku }} — {{ it.name }}</option>
        </select>
        <input v-model="line.quantity_ordered" type="number" step="0.01" placeholder="Miktar" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        <input v-model="line.unit_price" type="number" step="0.01" placeholder="Birim Fiyat" class="w-28 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="button" class="text-sm text-blue-600" @click="addLine">+ Kalem ekle</button>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button type="submit" class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
        Taslak Oluştur
      </button>
    </form>

    <div class="mt-6 max-w-4xl space-y-4">
      <div v-for="order in salesCrm.orders" :key="order.id" class="rounded border border-neutral-200 p-4 dark:border-neutral-800">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-neutral-900 dark:text-neutral-100">SO-{{ order.id }} — {{ order.party_name }}</span>
            <span class="ml-2 text-sm text-neutral-500">{{ order.warehouse_code }} · Toplam {{ order.total }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm">{{ statusLabels[order.status] }}</span>
            <button
              v-if="order.status === 'draft'"
              class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              @click="confirm(order.id)"
            >
              Onayla
            </button>
          </div>
        </div>

        <table v-if="order.status !== 'draft' && order.status !== 'cancelled'" class="mt-3 w-full text-left text-xs">
          <thead>
            <tr class="text-neutral-500">
              <th class="py-1 pr-3">Ürün</th>
              <th class="py-1 pr-3 text-right">Sipariş</th>
              <th class="py-1 pr-3 text-right">Sevk Edilen</th>
              <th class="py-1 pr-3 text-right">Kalan</th>
              <th class="py-1 pr-3" v-if="order.status !== 'fulfilled'">Şimdi Sevk Et</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="line in order.lines" :key="line.id">
              <td class="py-1 pr-3">{{ line.item_sku }}</td>
              <td class="py-1 pr-3 text-right">{{ line.quantity_ordered }}</td>
              <td class="py-1 pr-3 text-right">{{ line.quantity_fulfilled }}</td>
              <td class="py-1 pr-3 text-right">{{ line.quantity_remaining }}</td>
              <td class="py-1 pr-3" v-if="order.status !== 'fulfilled'">
                <input
                  v-model="fulfillDrafts[line.id]"
                  type="number"
                  step="0.01"
                  class="w-20 rounded border border-neutral-300 px-1 py-0.5 dark:border-neutral-700 dark:bg-neutral-800"
                />
              </td>
            </tr>
          </tbody>
        </table>
        <button
          v-if="order.status === 'confirmed' || order.status === 'partially_fulfilled'"
          class="mt-2 text-xs text-blue-600 hover:underline"
          @click="fulfill(order.id, order.lines.map((l) => l.id))"
        >
          Sevk Et
        </button>
      </div>
    </div>
  </section>
</template>
