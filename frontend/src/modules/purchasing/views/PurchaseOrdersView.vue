<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useCatalogStore } from '@/core/stores/catalog'
import { useARAPStore } from '@/core/stores/arap'
import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import { usePurchasingStore, type POLineInput } from '@/modules/purchasing/stores/purchasing'

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
    error.value = 'Tedarikçi ve depo seçin.'
    return
  }
  try {
    const lines: POLineInput[] = form.lines
      .filter((l) => l.item !== null)
      .map((l) => ({ item: l.item as number, quantity_ordered: l.quantity_ordered, unit_price: l.unit_price }))
    await purchasing.createOrder(form.party, form.warehouse, form.order_date, lines)
    form.lines = [{ item: null, quantity_ordered: '1', unit_price: '0' }]
  } catch (e: any) {
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? 'Sipariş oluşturulamadı.'
  }
}

async function approve(id: number) {
  try {
    await purchasing.approveOrder(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Onaylanamadı.'
  }
}

async function send(id: number) {
  try {
    await purchasing.sendOrder(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Gönderilemedi.'
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
    error.value = e?.response?.data?.detail ?? 'Teslim alma başarısız.'
  }
}

const statusLabels: Record<string, string> = {
  draft: 'Taslak',
  sent: 'Gönderildi',
  partially_received: 'Kısmi Teslim',
  received: 'Teslim Alındı',
  cancelled: 'İptal',
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Satın Alma Siparişleri</h1>

    <form class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex gap-3">
        <select v-model.number="form.party" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Tedarikçi seçin</option>
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
      <div v-for="order in purchasing.orders" :key="order.id" class="rounded border border-neutral-200 p-4 dark:border-neutral-800">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-neutral-900 dark:text-neutral-100">PO-{{ order.id }} — {{ order.party_name }}</span>
            <span class="ml-2 text-sm text-neutral-500">{{ order.warehouse_code }} · Toplam {{ order.total }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm">{{ statusLabels[order.status] }}</span>
            <button
              v-if="order.status === 'draft' && order.requires_approval && !order.approved_at"
              class="rounded bg-amber-500 px-2 py-1 text-xs font-medium text-white hover:bg-amber-600"
              @click="approve(order.id)"
            >
              Onayla (eşik: 10000)
            </button>
            <button
              v-if="order.status === 'draft'"
              class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              @click="send(order.id)"
            >
              Gönder
            </button>
          </div>
        </div>

        <table v-if="order.status !== 'draft' && order.status !== 'cancelled'" class="mt-3 w-full text-left text-xs">
          <thead>
            <tr class="text-neutral-500">
              <th class="py-1 pr-3">Ürün</th>
              <th class="py-1 pr-3 text-right">Sipariş</th>
              <th class="py-1 pr-3 text-right">Teslim Alınan</th>
              <th class="py-1 pr-3 text-right">Kalan</th>
              <th class="py-1 pr-3" v-if="order.status !== 'received'">Şimdi Teslim Al</th>
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
          Teslim Al
        </button>
      </div>
    </div>
  </section>
</template>
