<script setup lang="ts">
import { onMounted, reactive } from 'vue'

import { useCatalogStore } from '@/core/stores/catalog'

// REQ-INV-001: shared product/service catalog (Core, not package-specific --
// referenced by Purchasing/Inventory/eventually Sales regardless of which
// packages a tenant has purchased).
const catalog = useCatalogStore()
onMounted(() => catalog.fetchItems())

const form = reactive({ sku: '', name: '', unit_of_measure: 'adet' })

async function submit() {
  if (!form.sku.trim() || !form.name.trim()) return
  await catalog.createItem({ ...form })
  form.sku = ''
  form.name = ''
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Ürün/Malzeme Kataloğu</h1>

    <form class="mt-4 flex max-w-xl items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">SKU</label>
        <input v-model="form.sku" required class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">Ad</label>
        <input v-model="form.name" required class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Birim</label>
        <input v-model="form.unit_of_measure" class="w-20 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Ekle</button>
    </form>

    <table class="mt-6 w-full max-w-2xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">SKU</th>
          <th class="py-2 pr-4">Ad</th>
          <th class="py-2 pr-4">Birim</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in catalog.items" :key="item.id" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4 font-mono">{{ item.sku }}</td>
          <td class="py-1.5 pr-4">{{ item.name }}</td>
          <td class="py-1.5 pr-4 text-neutral-500">{{ item.unit_of_measure }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
