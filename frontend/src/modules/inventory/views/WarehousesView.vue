<script setup lang="ts">
import { onMounted, reactive } from 'vue'

import { useInventoryStore } from '@/modules/inventory/stores/inventory'

// REQ-INV-002: warehouse master data.
const inventory = useInventoryStore()
onMounted(() => inventory.fetchWarehouses())

const form = reactive({ code: '', name: '' })

async function submit() {
  if (!form.code.trim() || !form.name.trim()) return
  await inventory.createWarehouse(form.code, form.name)
  form.code = ''
  form.name = ''
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Depolar</h1>

    <form class="mt-4 flex max-w-md items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Kod</label>
        <input v-model="form.code" required class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">Ad</label>
        <input v-model="form.name" required class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Ekle</button>
    </form>

    <table class="mt-6 w-full max-w-xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Kod</th>
          <th class="py-2 pr-4">Ad</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="wh in inventory.warehouses" :key="wh.id" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4 font-mono">{{ wh.code }}</td>
          <td class="py-1.5 pr-4">{{ wh.name }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
