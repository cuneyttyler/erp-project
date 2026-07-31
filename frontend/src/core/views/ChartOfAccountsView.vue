<script setup lang="ts">
import { onMounted } from 'vue'

import { useLedgerStore } from '@/core/stores/ledger'

// REQ-CORE-GL-001: browse the tenant's Chart of Accounts.
const ledger = useLedgerStore()
onMounted(() => ledger.fetchAccounts())
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Hesap Planı</h1>

    <table class="mt-4 w-full max-w-3xl text-left text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-neutral-500 dark:border-neutral-800">
          <th class="py-2 pr-4">Kod</th>
          <th class="py-2 pr-4">Hesap Adı</th>
          <th class="py-2 pr-4">Tür</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="account in ledger.accounts"
          :key="account.id"
          class="border-b border-neutral-100 dark:border-neutral-900"
        >
          <td class="py-1.5 pr-4 font-mono">{{ account.code }}</td>
          <td class="py-1.5 pr-4">{{ account.name }}</td>
          <td class="py-1.5 pr-4 text-neutral-500">{{ account.account_type }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
