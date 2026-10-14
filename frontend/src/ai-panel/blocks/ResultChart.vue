<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFormat } from '@/core/dashboard/format'
import RankedBars from '@/shared/components/RankedBars.vue'
import SeriesChart from '@/shared/components/SeriesChart.vue'

import type { ChartBlock } from '../store'

// A chart the assistant produced. The figures were computed by the
// backend (a grouped total over real records, or a registered reporting
// series) -- the model chooses what to chart, never the numbers -- and it's
// drawn with the same chart components as the home panel.
const props = defineProps<{ block: ChartBlock }>()

const { t, te } = useI18n()
const format = useFormat()

function seriesName(name: string): string {
  // A registered series has a translated name; a computed one is named
  // after what it totals ("sum of total") and reads fine as it is.
  if (props.block.series_name && te(`assistant.series.${props.block.series_name}`)) return t(`assistant.series.${props.block.series_name}`)
  return name === 'count' ? t('assistant.values.count') : name
}

function label(raw: string): string {
  if (!raw) return t('widgets.ui.unassigned')
  if (props.block.label_kind === 'month' && /^\d{4}-\d{2}$/.test(raw)) return format.month(raw)
  if (props.block.label_kind === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(raw)) return format.shortDate(raw)
  return format.keyed('widgets.status', raw)
}

const labels = computed(() => (props.block.series[0]?.points ?? []).map((point) => label(point.label)))
const series = computed(() => props.block.series.map((s) => ({ name: seriesName(s.name), values: s.points.map((point) => Number(point.value)) })))
const title = computed(() => props.block.title || series.value[0]?.name || '')

function formatValue(value: number, compact = false): string {
  return format.value(value, props.block.format, compact)
}
</script>

<template>
  <figure class="rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
    <figcaption class="mb-2 text-sm font-medium text-neutral-800 dark:text-neutral-200">{{ title }}</figcaption>
    <RankedBars v-if="block.chart === 'hbar'" :rows="labels.map((l, i) => ({ label: l, value: series[0].values[i] }))" :format-value="formatValue" />
    <SeriesChart v-else :title="title" :type="block.chart" :labels="labels" :series="series" :format-value="formatValue" :integer="block.format === 'number'" />
  </figure>
</template>
