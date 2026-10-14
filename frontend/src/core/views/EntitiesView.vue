<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'

import PageInsights from '@/core/dashboard/PageInsights.vue'
import DataTable, { type ColumnDef } from '@/shared/components/DataTable.vue'
import { useEntityStore } from '@/shared/stores/entity'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-CORE-ENT-001: manage the legal entities/companies under this tenant.
// The header switcher (App.vue) picks which one is "current"; this screen
// is where new ones get created and existing ones renamed.
const entity = useEntityStore()
onMounted(() => entity.fetchEntities())

const form = reactive({ name: '', code: '', currency: 'TRY' })

async function submit() {
  if (!form.name.trim() || !form.code.trim()) return
  await entity.createEntity({ ...form })
  form.name = ''
  form.code = ''
}

const columns = computed<ColumnDef[]>(() => [
  { key: 'code', label: t('common.code') },
  { key: 'name', label: t('entities.name') },
  { key: 'currency', label: t('common.currency') },
  { key: 'is_active', label: t('common.active'), type: 'boolean' },
])
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('entities.title') }}</h1>
    <p class="mt-1 text-sm text-neutral-500">
      {{ t('entities.subtitle') }}
    </p>
    <PageInsights screen-key="entities" :widgets="['entity_comparison']" :follow="entity.entities" />

    <form class="mt-4 flex max-w-xl items-end gap-2 rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
      <div class="flex-1">
        <label class="mb-1 block text-xs text-neutral-500">{{ t('entities.name') }}</label>
        <input v-model="form.name" required class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.code') }}</label>
        <input v-model="form.code" required class="w-24 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-neutral-500">{{ t('common.currency') }}</label>
        <input v-model="form.currency" class="w-20 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      </div>
      <button type="submit" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('common.add') }}</button>
    </form>

    <div class="mt-6">
      <DataTable screen-key="entities" :columns="columns" :rows="entity.entities" />
    </div>
  </section>
</template>
