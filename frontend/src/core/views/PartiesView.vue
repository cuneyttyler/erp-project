<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import { useARAPStore } from '@/core/stores/arap'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-CORE-AR-*/AP-*/REQ-CORE-ENT-001: unified customer/vendor master data,
// scoped to the current entity.
const arap = useARAPStore()
const entity = useEntityStore()
onMounted(() => arap.fetchParties())
watch(() => entity.currentEntityId, () => arap.fetchParties())

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

const columns = computed<ColumnDef[]>(() => [
  { key: 'name', label: t('common.name'), editable: true },
  {
    key: 'party_type',
    label: t('common.type'),
    editable: true,
    type: 'select',
    options: [
      { value: 'customer', label: t('common.customer') },
      { value: 'vendor', label: t('common.vendor') },
      { value: 'both', label: t('parties.both') },
    ],
  },
  { key: 'tax_id', label: t('parties.taxId'), editable: true },
  { key: 'email', label: t('common.email'), editable: true },
])

async function onCellEdit({ row, column, value }: { row: any; column: string; value: any }) {
  await arap.updateParty(row.id, { [column]: value })
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('parties.title') }}</h1>
    <PageInsights screen-key="parties" :widgets="['top_customers','top_vendors']" :follow="arap.parties" />

    <form
      class="mt-4 flex max-w-3xl flex-wrap items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800"
      @submit.prevent="submit"
    >
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.name') }}</label>
        <input v-model="form.name" required class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.type') }}</label>
        <select v-model="form.party_type" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option value="customer">{{ t('common.customer') }}</option>
          <option value="vendor">{{ t('common.vendor') }}</option>
          <option value="both">{{ t('parties.both') }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('parties.taxId') }}</label>
        <input v-model="form.tax_id" class="w-32 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.email') }}</label>
        <input v-model="form.email" type="email" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
        {{ t('common.add') }}
      </button>
    </form>

    <div class="mt-6">
      <DataTable screen-key="parties" :columns="columns" :rows="arap.parties" @cell-edit="onCellEdit" />
    </div>
  </section>
</template>
