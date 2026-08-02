<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useCatalogStore } from '@/core/stores/catalog'
import { usePOSStore, type CheckoutLineInput, type CheckoutPaymentInput, type PaymentMethod } from '@/modules/pos/stores/pos'
import { queueOfflineSale, flushOfflineQueue, isOnline, pendingOfflineCount } from '@/modules/pos/offlineQueue'
import { registerPOSServiceWorker } from '@/modules/pos/registerSW'

// REQ-POS-001: item scan/lookup, discounts, multiple payment methods.
// REQ-POS-008: if the checkout POST fails because the browser is offline
// (not because the server rejected it), the sale is queued locally
// (offlineQueue.ts) instead of lost -- see that module for the sync story.
const pos = usePOSStore()
const catalog = useCatalogStore()

const openShiftId = ref<number | null>(null)

onMounted(async () => {
  registerPOSServiceWorker()
  await Promise.all([pos.fetchShifts(), catalog.fetchItems(), pos.fetchTills()])
  const openShift = pos.shifts.find((s) => s.status === 'open')
  openShiftId.value = openShift?.id ?? null
  flushOfflineQueue(pos)
})

window.addEventListener('online', () => flushOfflineQueue(pos))

interface CartLine {
  item_id: number
  sku: string
  name: string
  quantity: string
  unit_price: string
  discount_amount: string
}

const cart = ref<CartLine[]>([])
const pickerItemId = ref<number | null>(null)
const pickerQuantity = ref('1')
const pickerUnitPrice = ref('0.00')

const cartTotal = computed(() =>
  cart.value
    .reduce((sum, l) => sum + Number(l.quantity) * Number(l.unit_price) - Number(l.discount_amount || 0), 0)
    .toFixed(2),
)

function addToCart() {
  if (pickerItemId.value === null) return
  const item = catalog.items.find((i) => i.id === pickerItemId.value)
  if (!item) return
  cart.value.push({
    item_id: item.id,
    sku: item.sku,
    name: item.name,
    quantity: pickerQuantity.value,
    unit_price: pickerUnitPrice.value,
    discount_amount: '0',
  })
  pickerItemId.value = null
  pickerQuantity.value = '1'
  pickerUnitPrice.value = '0.00'
}

function removeLine(index: number) {
  cart.value.splice(index, 1)
}

const paymentMethod = ref<PaymentMethod>('cash')
const error = ref('')
const lastReceipt = ref<{ id: number; subtotal: string } | 'queued' | null>(null)

async function checkout() {
  error.value = ''
  lastReceipt.value = null
  if (openShiftId.value === null) {
    error.value = 'Önce bir vardiya açmalısınız (Vardiyalar sayfası).'
    return
  }
  if (cart.value.length === 0) {
    error.value = 'Sepet boş.'
    return
  }

  const lines: CheckoutLineInput[] = cart.value.map((l) => ({
    item_id: l.item_id,
    quantity: l.quantity,
    unit_price: l.unit_price,
    discount_amount: l.discount_amount,
  }))
  const payments: CheckoutPaymentInput[] = [{ method: paymentMethod.value, amount: cartTotal.value }]
  const clientReference = crypto.randomUUID()

  if (!isOnline()) {
    await queueOfflineSale({ shiftId: openShiftId.value, lines, payments, clientReference })
    lastReceipt.value = 'queued'
    cart.value = []
    return
  }

  try {
    const sale = await pos.checkout(openShiftId.value, lines, payments, clientReference)
    lastReceipt.value = { id: sale.id, subtotal: sale.subtotal }
    cart.value = []
  } catch (e: any) {
    if (!e?.response) {
      // No response at all -- a network failure, not a validation error the
      // server rejected. Queue it rather than lose the sale (REQ-POS-008).
      await queueOfflineSale({ shiftId: openShiftId.value, lines, payments, clientReference })
      lastReceipt.value = 'queued'
      cart.value = []
    } else {
      error.value = e.response?.data?.detail ?? 'Satış tamamlanamadı.'
    }
  }
}
</script>

<template>
  <section class="p-8">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Kasa (POS)</h1>
      <div class="flex items-center gap-3 text-xs">
        <span v-if="pendingOfflineCount > 0" class="rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          {{ pendingOfflineCount }} satış senkronizasyon bekliyor
        </span>
        <span :class="isOnline() ? 'text-green-600' : 'text-red-600'">{{ isOnline() ? '● Çevrimiçi' : '● Çevrimdışı' }}</span>
      </div>
    </div>

    <p v-if="openShiftId === null" class="mt-2 text-sm text-amber-700 dark:text-amber-400">
      Açık vardiya bulunamadı -- <RouterLink to="/pos/shifts" class="underline">Vardiyalar</RouterLink> sayfasından bir vardiya açın.
    </p>

    <div class="mt-4 grid grid-cols-3 gap-6">
      <div class="col-span-2">
        <div class="flex flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800">
          <div class="flex-1">
            <label class="mb-1 block text-xs text-neutral-500">Ürün</label>
            <select v-model.number="pickerItemId" data-testid="pos-item-select" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
              <option :value="null" disabled>Ürün seçin</option>
              <option v-for="i in catalog.items" :key="i.id" :value="i.id">{{ i.sku }} — {{ i.name }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs text-neutral-500">Adet</label>
            <input v-model="pickerQuantity" data-testid="pos-quantity-input" class="w-20 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-neutral-500">Birim Fiyat</label>
            <input v-model="pickerUnitPrice" data-testid="pos-price-input" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
          </div>
          <button type="button" data-testid="pos-add-to-cart" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700" @click="addToCart">
            Sepete Ekle
          </button>
        </div>

        <table class="mt-4 w-full text-sm">
          <thead>
            <tr class="border-b border-neutral-200 text-left text-xs text-neutral-500 dark:border-neutral-800">
              <th class="py-1">Ürün</th>
              <th class="py-1">Adet</th>
              <th class="py-1">Birim Fiyat</th>
              <th class="py-1">İndirim</th>
              <th class="py-1">Tutar</th>
              <th class="py-1"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(line, idx) in cart" :key="idx" class="border-b border-neutral-100 dark:border-neutral-900">
              <td class="py-1">{{ line.sku }} — {{ line.name }}</td>
              <td class="py-1">{{ line.quantity }}</td>
              <td class="py-1">{{ line.unit_price }}</td>
              <td class="py-1"><input v-model="line.discount_amount" class="w-16 rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800" /></td>
              <td class="py-1">{{ (Number(line.quantity) * Number(line.unit_price) - Number(line.discount_amount || 0)).toFixed(2) }}</td>
              <td class="py-1"><button class="text-xs text-red-600 hover:underline" @click="removeLine(idx)">Sil</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="rounded border border-neutral-200 p-4 dark:border-neutral-800">
        <p class="text-sm text-neutral-500">Toplam</p>
        <p class="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{{ cartTotal }} ₺</p>

        <label class="mt-4 mb-1 block text-xs text-neutral-500">Ödeme Yöntemi</label>
        <select v-model="paymentMethod" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option value="cash">Nakit</option>
          <option value="card">Kart</option>
        </select>

        <button
          type="button"
          class="mt-4 w-full rounded bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          :disabled="cart.length === 0"
          @click="checkout"
        >
          Tahsil Et
        </button>

        <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
        <p v-if="lastReceipt === 'queued'" class="mt-2 text-sm text-amber-700 dark:text-amber-400">
          Bağlantı yok -- satış çevrimdışı kuyruğa alındı, bağlantı gelince otomatik gönderilecek.
        </p>
        <p v-else-if="lastReceipt" class="mt-2 text-sm text-green-700 dark:text-green-400">
          Satış #{{ lastReceipt.id }} tamamlandı ({{ lastReceipt.subtotal }} ₺).
        </p>
      </div>
    </div>
  </section>
</template>
