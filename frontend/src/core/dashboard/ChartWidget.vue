<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import RankedBars from '@/shared/components/RankedBars.vue'
import SeriesChart from '@/shared/components/SeriesChart.vue'

import { useFormat } from './format'
import type { ChartData } from './types'

const props = defineProps<{ data: ChartData; title: string }>()

const { t } = useI18n()
const format = useFormat()

function printLabel(label: string): string {
  const isDate = /^\d{4}-\d{2}-\d{2}$/.test(label)
  if (props.data.label_kind === 'month') return format.month(label)
  // A date axis can still carry a named bucket (e.g. "overdue" ahead of
  // the weeks in the cash forecast).
  if (props.data.label_kind === 'date') return isDate ? format.shortDate(label) : format.keyed('widgets.labels', label)
  if (props.data.label_kind === 'key') return format.keyed('widgets.labels', label)
  return label || t('widgets.ui.unassigned')
}

const labels = computed(() => (props.data.series[0]?.points ?? []).map((point) => printLabel(point.label)))
const series = computed(() =>
  props.data.series.map((s) => ({
    name: t(`widgets.series.${s.key}`),
    values: s.points.map((point) => Number(point.value)),
  })),
)
const rankedRows = computed(() => labels.value.map((label, i) => ({ label, value: series.value[0].values[i] })))

// Nothing but zeros (or no points at all) is "no data", not a chart of a
// flat line along the baseline.
const isEmpty = computed(() => series.value.every((s) => s.values.every((value) => value === 0)))

function formatValue(value: number, compact = false): string {
  return format.value(value, props.data.format, compact)
}
</script>

<template>
  <p v-if="isEmpty" class="py-8 text-center text-sm text-neutral-500">{{ t('widgets.ui.noData') }}</p>
  <RankedBars v-else-if="data.chart === 'hbar'" :rows="rankedRows" :format-value="formatValue" />
  <SeriesChart
    v-else
    :title="title"
    :type="data.chart"
    :labels="labels"
    :series="series"
    :format-value="formatValue"
    :integer="data.format === 'number'"
  />
</template>
