<script setup lang="ts">
import { onMounted, reactive } from 'vue'

import { useEntityStore } from '@/shared/stores/entity'
import { useInventoryStore } from '@/modules/inventory/stores/inventory'
import { usePOSStore } from '@/modules/pos/stores/pos'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-POS-002: multi-store/multi-till configuration. One screen for both,
// since a till is meaningless without a store to pick it from -- splitting
// this into two nav items would just make setup slower for what's a
// once-per-store, rarely-repeated task.
const pos = usePOSStore()
const entity = useEntityStore()
const inventory = useInventoryStore()

onMounted(() => {
  pos.fetchStores()
  pos.fetchTills()
  entity.fetchEntities()
  inventory.fetchWarehouses()
})

const storeForm = reactive({ entity: null as number | null, warehouse: null as number | null, code: '', name: '' })
async function createStore() {
  if (storeForm.entity === null || storeForm.warehouse === null || !storeForm.code.trim() || !storeForm.name.trim()) return
  await pos.createStore({ entity: storeForm.entity, warehouse: storeForm.warehouse, code: storeForm.code, name: storeForm.name })
  storeForm.code = ''
  storeForm.name = ''
}

const tillForm = reactive({ store: null as number | null, code: '', name: '' })
async function createTill() {
  if (tillForm.store === null || !tillForm.code.trim() || !tillForm.name.trim()) return
  await pos.createTill({ store: tillForm.store, code: tillForm.code, name: tillForm.name })
  tillForm.code = ''
  tillForm.name = ''
}

const storeColumns: ColumnDef[] = [
  { key: 'code', label: 'Kod' },
  { key: 'name', label: 'Mağaza' },
  { key: 'entity_code', label: 'Şirket' },
  { key: 'warehouse_code', label: 'Depo' },
  { key: 'is_active', label: 'Aktif', type: 'boolean' },
]
const tillColumns: ColumnDef[] = [
  { key: 'store_code', label: 'Mağaza' },
  { key: 'code', label: 'Kod' },
  { key: 'name', label: 'Kasa' },
  { key: 'is_active', label: 'Aktif', type: 'boolean' },
]
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Mağaza ve Kasa Ayarları</h1>

    <h2 class="mt-6 text-sm font-semibold text-neutral-700 dark:text-neutral-300">Mağazalar</h2>
    <form class="mt-2 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="createStore">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Şirket</label>
        <select v-model.number="storeForm.entity" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Seçin</option>
          <option v-for="e in entity.entities" :key="e.id" :value="e.id">{{ e.code }} — {{ e.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Depo</label>
        <select v-model.number="storeForm.warehouse" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Seçin</option>
          <option v-for="w in inventory.warehouses" :key="w.id" :value="w.id">{{ w.code }} — {{ w.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Kod</label>
        <input v-model="storeForm.code" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">Mağaza Adı</label>
        <input v-model="storeForm.name" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Ekle</button>
    </form>
    <div class="mt-3">
      <DataTable screen-key="pos-stores" :columns="storeColumns" :rows="pos.stores" />
    </div>

    <h2 class="mt-8 text-sm font-semibold text-neutral-700 dark:text-neutral-300">Kasalar</h2>
    <form class="mt-2 flex max-w-2xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="createTill">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Mağaza</label>
        <select v-model.number="tillForm.store" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Seçin</option>
          <option v-for="s in pos.stores" :key="s.id" :value="s.id">{{ s.code }} — {{ s.name }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Kod</label>
        <input v-model="tillForm.code" class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">Kasa Adı</label>
        <input v-model="tillForm.name" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Ekle</button>
    </form>
    <div class="mt-3">
      <DataTable screen-key="pos-tills" :columns="tillColumns" :rows="pos.tills" />
    </div>
  </section>
</template>
