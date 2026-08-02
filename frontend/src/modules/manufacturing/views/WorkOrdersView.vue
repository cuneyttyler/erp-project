<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import { useManufacturingStore } from '@/modules/manufacturing/stores/manufacturing'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-MFG-002: create, release, and complete work orders.
const manufacturing = useManufacturingStore()
const inventory = useInventoryStore()

onMounted(() => {
  manufacturing.fetchBOMs()
  manufacturing.fetchWorkOrders()
  inventory.fetchWarehouses()
})

const form = reactive({
  bom: null as number | null,
  warehouse: null as number | null,
  quantity_planned: '1',
  scheduled_date: new Date().toISOString().slice(0, 10),
})
const error = ref('')
const completeDrafts = reactive<Record<number, string>>({})

async function submit() {
  error.value = ''
  if (form.bom === null || form.warehouse === null) {
    error.value = 'Reçete ve depo seçin.'
    return
  }
  try {
    await manufacturing.createWorkOrder(form.bom, form.warehouse, form.quantity_planned, form.scheduled_date)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'İş emri oluşturulamadı.'
  }
}

async function release(id: number) {
  try {
    await manufacturing.releaseWorkOrder(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Serbest bırakılamadı.'
  }
}

async function complete(id: number) {
  const qty = completeDrafts[id] || '0'
  if (parseFloat(qty) <= 0) return
  try {
    await manufacturing.completeWorkOrder(id, qty)
    completeDrafts[id] = ''
    error.value = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Tamamlanamadı.'
  }
}

const statusLabels: Record<string, string> = {
  draft: 'Taslak',
  released: 'Serbest Bırakıldı',
  in_progress: 'Devam Ediyor',
  completed: 'Tamamlandı',
  cancelled: 'İptal',
}

const columns: ColumnDef[] = [
  { key: 'bom_item_sku', label: 'Ürün' },
  { key: 'warehouse_code', label: 'Depo' },
  { key: 'quantity_planned', label: 'Planlanan', type: 'number' },
  { key: 'quantity_completed', label: 'Tamamlanan', type: 'number' },
  { key: 'status', label: 'Durum' },
  { key: 'actions', label: '', sortable: false, filterable: false },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">İş Emirleri</h1>

    <form class="mt-4 flex max-w-2xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <select v-model.number="form.bom" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
        <option :value="null" disabled>Reçete seçin</option>
        <option v-for="b in manufacturing.boms" :key="b.id" :value="b.id">{{ b.item_sku }} — {{ b.name }}</option>
      </select>
      <select v-model.number="form.warehouse" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
        <option :value="null" disabled>Depo seçin</option>
        <option v-for="w in inventory.warehouses" :key="w.id" :value="w.id">{{ w.code }} — {{ w.name }}</option>
      </select>
      <input v-model="form.quantity_planned" type="number" step="0.01" placeholder="Planlanan Miktar" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <input v-model="form.scheduled_date" type="date" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Oluştur</button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <div class="mt-6">
      <DataTable screen-key="work-orders" :columns="columns" :rows="manufacturing.workOrders">
        <template #status="{ row }">{{ statusLabels[row.status] }}</template>
        <template #actions="{ row }">
          <button v-if="row.status === 'draft'" class="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700" @click="release(row.id)">
            Serbest Bırak
          </button>
          <template v-if="row.status === 'released' || row.status === 'in_progress'">
            <input v-model="completeDrafts[row.id]" type="number" step="0.01" class="w-20 rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-800" />
            <button class="text-xs text-blue-600 hover:underline" @click="complete(row.id)">Tamamla</button>
          </template>
        </template>
      </DataTable>
    </div>
  </section>
</template>
