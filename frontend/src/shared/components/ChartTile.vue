<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// A single-series chart tile (REQ-BI-001/002) -- bar for a "category"
// series (identity/ranking), line for a "time" series (magnitude over
// time). Single-series only: no legend box (the title already names what's
// plotted, per the dataviz skill's "a single series needs no legend"),
// just the one categorical slot (series-1 blue) from the validated default
// palette (see dataviz skill references/palette.md) -- swap CSS variables
// below if/when this product adopts its own brand palette.

const props = defineProps<{
  title: string
  chartKind: 'time' | 'category'
  data: { label: string; value: string }[]
}>()

const points = computed(() => props.data.map((d) => ({ label: d.label, value: Number(d.value) })))
const maxValue = computed(() => Math.max(...points.value.map((p) => p.value), 0.01))

const hoverIndex = ref<number | null>(null)

// Bar geometry
const barWidth = 24
const gap = 8
const chartHeight = 160
const chartWidth = computed(() => points.value.length * (barWidth + gap) + gap)

function barHeight(value: number) {
  return (value / maxValue.value) * (chartHeight - 24)
}

// Line geometry (time series) -- same viewBox height, points spread evenly
const linePoints = computed(() =>
  points.value.map((p, i) => {
    const x = points.value.length > 1 ? (i / (points.value.length - 1)) * (chartWidth.value - 16) + 8 : chartWidth.value / 2
    const y = chartHeight - 12 - barHeight(p.value)
    return { x, y, ...p }
  }),
)
const linePath = computed(() => linePoints.value.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' '))

function formatValue(value: number): string {
  return value.toLocaleString('tr-TR', { maximumFractionDigits: 0 })
}
</script>

<template>
  <div class="viz-root rounded border border-neutral-200 p-4 dark:border-neutral-800">
    <h3 class="text-sm font-medium text-[var(--text-primary)]">{{ title }}</h3>

    <div v-if="points.length === 0" class="mt-6 text-sm text-[var(--text-secondary)]">{{ t('common.noData') }}</div>

    <svg v-else :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="mt-3 w-full" :style="{ height: '180px' }">
      <line x1="0" :x2="chartWidth" :y1="chartHeight - 12" :y2="chartHeight - 12" stroke="var(--baseline)" stroke-width="1" />

      <template v-if="chartKind === 'category'">
        <g v-for="(p, i) in points" :key="p.label" @mouseenter="hoverIndex = i" @mouseleave="hoverIndex = null">
          <rect
            :x="gap + i * (barWidth + gap)"
            :y="chartHeight - 12 - barHeight(p.value)"
            :width="barWidth"
            :height="Math.max(barHeight(p.value), 1)"
            rx="4"
            fill="var(--series-1)"
            :opacity="hoverIndex === null || hoverIndex === i ? 1 : 0.55"
          />
        </g>
      </template>

      <template v-else>
        <path :d="linePath" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        <circle
          v-for="(p, i) in linePoints"
          :key="p.label"
          :cx="p.x"
          :cy="p.y"
          r="4"
          fill="var(--series-1)"
          stroke="var(--surface-1)"
          stroke-width="2"
          @mouseenter="hoverIndex = i"
          @mouseleave="hoverIndex = null"
        />
      </template>
    </svg>

    <div class="mt-1 flex justify-between text-xs text-[var(--text-muted)]">
      <span>{{ points[0]?.label }}</span>
      <span v-if="points.length > 1">{{ points[points.length - 1]?.label }}</span>
    </div>

    <div v-if="hoverIndex !== null && points[hoverIndex]" class="mt-2 rounded border border-neutral-200 px-2 py-1 text-xs dark:border-neutral-800">
      <span class="text-[var(--text-secondary)]">{{ points[hoverIndex].label }}:</span>
      <span class="ml-1 font-medium text-[var(--text-primary)]">{{ formatValue(points[hoverIndex].value) }}</span>
    </div>

    <table class="sr-only">
      <caption>{{ title }}</caption>
      <thead><tr><th>{{ t('common.label') }}</th><th>{{ t('common.value') }}</th></tr></thead>
      <tbody>
        <tr v-for="p in points" :key="p.label"><td>{{ p.label }}</td><td>{{ p.value }}</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.viz-root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --baseline: #c3c2b7;
  --series-1: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --baseline: #383835;
    --series-1: #3987e5;
  }
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
