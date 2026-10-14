<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { TableBlock } from '../store'
import { useValues } from './values'

// Records the assistant looked up, as a table. The rows come straight from
// the resource's API (through the assistant's query tool), so what's shown
// here is exactly what the matching screen would show.
defineProps<{ block: TableBlock }>()

const { t } = useI18n()
const values = useValues()
</script>

<template>
  <figure class="rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
    <figcaption v-if="block.title" class="border-b border-neutral-200 px-3 py-2 text-sm font-medium text-neutral-800 dark:border-neutral-800 dark:text-neutral-200">
      {{ block.title }}
    </figcaption>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-neutral-200 text-xs text-neutral-500 dark:border-neutral-800">
            <th
              v-for="column in block.columns"
              :key="column"
              class="whitespace-nowrap px-3 py-2 font-medium"
              :class="values.isNumeric(block.rows[0]?.[column]) ? 'text-right' : 'text-left'"
            >
              {{ values.label(column) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in block.rows" :key="index" class="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60">
            <td
              v-for="column in block.columns"
              :key="column"
              class="max-w-64 truncate px-3 py-1.5 text-neutral-800 dark:text-neutral-200"
              :class="values.isNumeric(row[column]) ? 'text-right tabular-nums' : 'text-left'"
              :title="values.text(column, row[column])"
            >
              {{ values.text(column, row[column]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="block.total > block.rows.length" class="border-t border-neutral-200 px-3 py-1.5 text-xs text-neutral-500 dark:border-neutral-800">
      {{ t('widgets.ui.showing', { shown: block.rows.length, total: block.total }) }}
    </p>
  </figure>
</template>
