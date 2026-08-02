<script setup lang="ts">
import { onMounted, watch } from 'vue'

import { useLedgerStore } from '@/core/stores/ledger'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'

// REQ-CORE-GL-001/REQ-CORE-ENT-001: browse the current entity's Chart of
// Accounts, re-fetching whenever the header's entity switcher changes.
const ledger = useLedgerStore()
const entity = useEntityStore()
onMounted(() => ledger.fetchAccounts())
watch(() => entity.currentEntityId, () => ledger.fetchAccounts())

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
