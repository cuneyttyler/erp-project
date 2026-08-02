<script setup lang="ts">
import { onMounted } from 'vue'

import { useLedgerStore } from '@/core/stores/ledger'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'

// REQ-CORE-GL-001: browse the tenant's Chart of Accounts.
const ledger = useLedgerStore()
onMounted(() => ledger.fetchAccounts())

const columns: ColumnDef[] = [
  { key: 'code', label: 'Kod' },
  { key: 'name', label: 'Hesap Adı', editable: true },
  { key: 'account_type', label: 'Tür' },
]

async function onCellEdit({ row, column, value }: { row: any; column: string; value: any }) {
  await ledger.updateAccount(row.id, { [column]: value })
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Hesap Planı</h1>

    <div class="mt-4">
      <DataTable screen-key="accounts" :columns="columns" :rows="ledger.accounts" @cell-edit="onCellEdit" />
    </div>
  </section>
</template>
