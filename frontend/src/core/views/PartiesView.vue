<script setup lang="ts">
import { onMounted, reactive } from 'vue'

import { useARAPStore } from '@/core/stores/arap'

// REQ-CORE-AR-*/AP-*: unified customer/vendor master data.
const arap = useARAPStore()
onMounted(() => arap.fetchParties())

const form = reactive({
  name: '',
  party_type: 'customer' as 'customer' | 'vendor' | 'both',
  tax_id: '',
  email: '',
  phone: '',
})

async function submit() {
  if (!form.name.trim()) return
  await arap.createParty({ ...form })
  form.name = ''
  form.tax_id = ''
  form.email = ''
  form.phone = ''
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Cari Hesaplar</h1>

    <form
      class="mt-4 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800"
      @submit.prevent="submit"
    >
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Ad</label>
        <input v-model="form.name" required class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">Tür</label>
        <select v-model="form.party_type" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option value="customer">Müşteri</option>
          <option value="vendor">Tedarikçi</option>
          <option value="both">Her ikisi</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">VKN/TCKN</label>
        <input v-model="form.tax_id" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">E-posta</label>
        <input v-model="form.email" type="email" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
        Ekle
      </button>
    </form>

    <table class="mt-6 w-full max-w-3xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Ad</th>
          <th class="py-2 pr-4">Tür</th>
          <th class="py-2 pr-4">VKN/TCKN</th>
          <th class="py-2 pr-4">E-posta</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in arap.parties" :key="p.id" class="border-b border-neutral-100 dark:border-neutral-900">
          <td class="py-1.5 pr-4">{{ p.name }}</td>
          <td class="py-1.5 pr-4 text-neutral-500">{{ p.party_type }}</td>
          <td class="py-1.5 pr-4 font-mono">{{ p.tax_id }}</td>
          <td class="py-1.5 pr-4">{{ p.email }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
