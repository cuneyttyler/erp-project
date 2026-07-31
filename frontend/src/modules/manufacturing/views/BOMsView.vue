<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useCatalogStore } from '@/core/stores/catalog'
import { useManufacturingStore, type BOMLineInput } from '@/modules/manufacturing/stores/manufacturing'

// REQ-MFG-001: Bill of Materials definition.
const manufacturing = useManufacturingStore()
const catalog = useCatalogStore()

onMounted(() => {
  manufacturing.fetchBOMs()
  catalog.fetchItems()
})

const form = reactive({
  item: null as number | null,
  name: '',
  lines: [{ component_item: null as number | null, quantity_per: '1' }],
})
const error = ref('')

function addLine() {
  form.lines.push({ component_item: null, quantity_per: '1' })
}

async function submit() {
  error.value = ''
  if (form.item === null || !form.name.trim()) {
    error.value = 'Mamul ürün ve ad girin.'
    return
  }
  try {
    const lines: BOMLineInput[] = form.lines
      .filter((l) => l.component_item !== null)
      .map((l) => ({ component_item: l.component_item as number, quantity_per: l.quantity_per }))
    await manufacturing.createBOM(form.item, form.name, lines)
    form.name = ''
    form.lines = [{ component_item: null, quantity_per: '1' }]
  } catch (e: any) {
    error.value = e?.response?.data?.lines?.[0] ?? e?.response?.data?.detail ?? 'Reçete oluşturulamadı.'
  }
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Ürün Reçeteleri (BOM)</h1>

    <form class="mt-4 max-w-2xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex gap-3">
        <select v-model.number="form.item" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Mamul ürün seçin</option>
          <option v-for="it in catalog.items" :key="it.id" :value="it.id">{{ it.sku }} — {{ it.name }}</option>
        </select>
        <input v-model="form.name" placeholder="Reçete adı" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>

      <div v-for="(line, i) in form.lines" :key="i" class="flex items-center gap-2">
        <select v-model.number="line.component_item" class="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>Bileşen seçin</option>
          <option v-for="it in catalog.items" :key="it.id" :value="it.id">{{ it.sku }} — {{ it.name }}</option>
        </select>
        <input v-model="line.quantity_per" type="number" step="0.0001" placeholder="Birim başına miktar" class="w-40 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="button" class="text-sm text-blue-600" @click="addLine">+ Bileşen ekle</button>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button type="submit" class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
        Reçete Oluştur
      </button>
    </form>

    <div class="mt-6 max-w-3xl space-y-3">
      <div v-for="bom in manufacturing.boms" :key="bom.id" class="rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
        <p class="font-medium text-neutral-900 dark:text-neutral-100">{{ bom.item_sku }} — {{ bom.name }}</p>
        <ul class="mt-1 text-neutral-500">
          <li v-for="line in bom.lines" :key="line.id">{{ line.component_sku }} x{{ line.quantity_per }}</li>
        </ul>
      </div>
    </div>
  </section>
</template>
