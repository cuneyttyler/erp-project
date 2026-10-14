<script setup lang="ts">
import { computed } from 'vue'

import { useValues } from './values'

// A record's fields as label/value pairs, with any nested list of rows
// (an invoice's lines, a journal entry's lines) as a small table beneath.
// Shared by the record card and the proposal card.
const props = defineProps<{ fields: Record<string, unknown> }>()

const values = useValues()

function isRowList(value: unknown): value is Record<string, unknown>[] {
  return Array.isArray(value) && value.length > 0 && value.every((item) => item !== null && typeof item === 'object' && !Array.isArray(item))
}

const scalars = computed(() => Object.entries(props.fields).filter(([, value]) => !isRowList(value)))
const lists = computed(() =>
  Object.entries(props.fields)
    .filter((entry): entry is [string, Record<string, unknown>[]] => isRowList(entry[1]))
    .map(([field, rows]) => ({ field, rows, columns: Object.keys(rows[0]).filter((column) => typeof rows[0][column] !== 'object' || rows[0][column] === null) })),
)
</script>

<template>
  <div>
    <dl class="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-4 gap-y-1 text-sm">
      <template v-for="[field, value] in scalars" :key="field">
        <dt class="truncate text-neutral-500">{{ values.label(field) }}</dt>
        <dd class="break-words text-neutral-900 dark:text-neutral-100">{{ values.text(field, value) }}</dd>
      </template>
    </dl>
    <div v-for="list in lists" :key="list.field" class="mt-3">
      <p class="mb-1 text-xs font-medium text-neutral-500">{{ values.label(list.field) }}</p>
      <div class="overflow-x-auto rounded border border-neutral-200 dark:border-neutral-800">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-neutral-200 text-xs text-neutral-500 dark:border-neutral-800">
              <th v-for="column in list.columns" :key="column" class="whitespace-nowrap px-2 py-1 text-left font-medium">{{ values.label(column) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in list.rows" :key="index" class="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60">
              <td v-for="column in list.columns" :key="column" class="px-2 py-1 text-neutral-800 dark:text-neutral-200">{{ values.text(column, row[column]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
