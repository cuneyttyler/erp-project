<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useFormat } from './format'
import type { ColumnKind, TableData } from './types'

defineProps<{ data: TableData }>()

const { t } = useI18n()
const format = useFormat()

const NUMERIC: ColumnKind[] = ['money', 'number']

// The few statuses that mean "act on this" get a status color; every other
// status is a neutral label. Each is still spelled out in words, so the
// color only reinforces it.
const STATUS_TONE: Record<string, string> = {
  overdue: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300',
  failed: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300',
  due_soon: 'bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
}
const NEUTRAL_TONE = 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300'

function cell(value: string | number | null, kind: ColumnKind): string {
  if (value === null || value === '') return '—'
  if (kind === 'money') return format.money(Number(value))
  if (kind === 'number') return format.number(Number(value))
  if (kind === 'date') return format.date(String(value))
  if (kind === 'datetime') return format.dateTime(String(value))
  if (kind === 'status') return format.keyed('widgets.status', String(value))
  return String(value)
}
</script>

<template>
  <p v-if="data.rows.length === 0" class="py-8 text-center text-sm text-neutral-500">{{ t('widgets.ui.nothingHere') }}</p>
  <div v-else class="-mx-4 overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-xs text-neutral-500 dark:border-neutral-800">
          <th
            v-for="column in data.columns"
            :key="column.key"
            class="whitespace-nowrap px-4 pb-2 font-medium"
            :class="NUMERIC.includes(column.kind) ? 'text-right' : 'text-left'"
          >
            {{ t(`widgets.columns.${column.key}`) }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in data.rows" :key="i" class="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60">
          <td
            v-for="column in data.columns"
            :key="column.key"
            class="px-4 py-2 text-neutral-800 dark:text-neutral-200"
            :class="[
              NUMERIC.includes(column.kind) ? 'text-right tabular-nums' : 'text-left',
              column.kind === 'text' ? 'max-w-56 truncate' : 'whitespace-nowrap',
            ]"
            :title="column.kind === 'text' ? cell(row[column.key], column.kind) : undefined"
          >
            <span
              v-if="column.kind === 'status' && row[column.key]"
              class="rounded px-1.5 py-0.5 text-xs font-medium"
              :class="STATUS_TONE[String(row[column.key])] ?? NEUTRAL_TONE"
            >
              {{ cell(row[column.key], column.kind) }}
            </span>
            <template v-else>{{ cell(row[column.key], column.kind) }}</template>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="data.total_count > data.rows.length" class="px-4 pt-2 text-xs text-neutral-500">
      {{ t('widgets.ui.showing', { shown: data.rows.length, total: data.total_count }) }}
    </p>
  </div>
</template>
