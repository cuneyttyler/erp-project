<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

// A line or vertical-bar chart for one or more series sharing one label
// axis and ONE value axis (never dual-axis). Built to the same dataviz
// method as ChartTile.vue -- thin marks, hairline solid grid, 4px rounded
// data-ends anchored to the baseline, a legend whenever there are two or
// more series, a hover/keyboard tooltip that enhances rather than gates
// (every value is also in the visually-hidden table) -- but sized to its
// container and multi-series, which ChartTile (single series, fixed
// geometry) isn't. Series colors are the validated default categorical
// palette in fixed slot order; a third series would take slot 3 (aqua).
const props = withDefaults(
  defineProps<{
    title: string
    type: 'line' | 'bar'
    labels: string[]
    series: { name: string; values: number[] }[]
    formatValue: (value: number, compact?: boolean) => string
    // Counts, not amounts: keep the axis on whole numbers.
    integer?: boolean
  }>(),
  { integer: false },
)

const SERIES_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)']
const HEIGHT = 208
const MARGIN = { right: 8, bottom: 24, left: 52 }
const MAX_BAR_WIDTH = 24
const BAR_GAP = 2

const root = ref<HTMLElement | null>(null)
const width = ref(480)
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!root.value) return
  width.value = root.value.clientWidth || width.value
  observer = new ResizeObserver((entries) => {
    width.value = entries[0].contentRect.width || width.value
  })
  observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

const count = computed(() => props.labels.length)
// Few enough single-series bars to label every cap directly without the
// labels colliding; beyond that the axis and tooltip carry the values.
const capLabels = computed(() => props.type === 'bar' && props.series.length === 1 && count.value <= 6)
const marginTop = computed(() => (capLabels.value ? 22 : 10))
const innerWidth = computed(() => Math.max(width.value - MARGIN.left - MARGIN.right, 40))
const innerHeight = computed(() => HEIGHT - marginTop.value - MARGIN.bottom)
const band = computed(() => innerWidth.value / Math.max(count.value, 1))

const scale = computed(() => {
  const all = props.series.flatMap((s) => s.values)
  const min = Math.min(0, ...all)
  const max = Math.max(0, ...all)
  const range = max - min || 1
  const raw = range / 4
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const normalized = raw / magnitude
  let step = (normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10) * magnitude
  if (props.integer) step = Math.max(1, Math.round(step))
  const lo = Math.floor(min / step) * step
  const hi = Math.max(Math.ceil(max / step) * step, lo + step)
  const ticks: number[] = []
  for (let tick = lo; tick <= hi + step / 2; tick += step) ticks.push(tick)
  return { lo, hi, ticks }
})

function y(value: number): number {
  const { lo, hi } = scale.value
  return marginTop.value + innerHeight.value * (1 - (value - lo) / (hi - lo))
}

function centerX(index: number): number {
  return MARGIN.left + band.value * (index + 0.5)
}

const barWidth = computed(() => {
  const k = props.series.length
  return Math.max(2, Math.min(MAX_BAR_WIDTH, (band.value * 0.7 - BAR_GAP * (k - 1)) / k))
})

function barX(index: number, seriesIndex: number): number {
  const k = props.series.length
  const groupWidth = k * barWidth.value + (k - 1) * BAR_GAP
  return MARGIN.left + band.value * index + (band.value - groupWidth) / 2 + seriesIndex * (barWidth.value + BAR_GAP)
}

// Rounded at the data end, square at the baseline -- for a negative value
// the data end is the bottom.
function barPath(index: number, seriesIndex: number, value: number): string {
  const x = barX(index, seriesIndex)
  const w = barWidth.value
  const base = y(0)
  const end = y(value)
  const r = Math.min(4, w / 2, Math.abs(base - end))
  const inward = end <= base ? r : -r
  return `M${x},${base} V${end + inward} Q${x},${end} ${x + r},${end} H${x + w - r} Q${x + w},${end} ${x + w},${end + inward} V${base} Z`
}

function linePath(values: number[]): string {
  return values.map((value, i) => `${i === 0 ? 'M' : 'L'}${centerX(i)},${y(value)}`).join(' ')
}

// Markers on every point only while they'd stay clear of each other.
const showMarkers = computed(() => count.value <= 14)

// As many x labels as fit, always including the last (most recent) one.
const labelStep = computed(() => Math.ceil(count.value / Math.max(1, Math.floor(innerWidth.value / 56))))
function showLabel(index: number): boolean {
  return (count.value - 1 - index) % labelStep.value === 0
}

const hoverIndex = ref<number | null>(null)

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  const delta = event.key === 'ArrowRight' ? 1 : -1
  const current = hoverIndex.value ?? (delta === 1 ? -1 : count.value)
  hoverIndex.value = Math.min(count.value - 1, Math.max(0, current + delta))
}

// Keeps the tooltip inside the card at either edge.
const tooltipStyle = computed(() => {
  if (hoverIndex.value === null) return {}
  const x = centerX(hoverIndex.value)
  if (x < 96) return { left: `${Math.max(x - 12, 0)}px` }
  if (x > width.value - 96) return { right: `${Math.max(width.value - x - 12, 0)}px` }
  return { left: `${x}px`, transform: 'translateX(-50%)' }
})
</script>

<template>
  <div class="viz-root">
    <ul v-if="series.length > 1" class="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]">
      <li v-for="(s, i) in series" :key="s.name" class="flex items-center gap-1.5">
        <span
          class="inline-block shrink-0"
          :class="type === 'line' ? 'h-0.5 w-3 rounded-full' : 'h-2.5 w-2.5 rounded-sm'"
          :style="{ background: SERIES_COLORS[i] }"
        />
        {{ s.name }}
      </li>
    </ul>

    <div
      ref="root"
      class="relative rounded outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      tabindex="0"
      role="img"
      :aria-label="title"
      @keydown="onKeydown"
      @blur="hoverIndex = null"
      @mouseleave="hoverIndex = null"
    >
      <svg :width="width" :height="HEIGHT" :viewBox="`0 0 ${width} ${HEIGHT}`" class="block">
        <g v-for="tick in scale.ticks" :key="tick">
          <line
            :x1="MARGIN.left"
            :x2="width - MARGIN.right"
            :y1="y(tick)"
            :y2="y(tick)"
            :stroke="tick === 0 ? 'var(--baseline)' : 'var(--gridline)'"
            stroke-width="1"
          />
          <text :x="MARGIN.left - 8" :y="y(tick)" dy="0.32em" text-anchor="end" class="axis-text">{{ formatValue(tick, true) }}</text>
        </g>

        <rect
          v-if="hoverIndex !== null && type === 'bar'"
          :x="MARGIN.left + band * hoverIndex"
          :y="marginTop"
          :width="band"
          :height="innerHeight"
          fill="var(--gridline)"
          opacity="0.5"
        />
        <line
          v-if="hoverIndex !== null && type === 'line'"
          :x1="centerX(hoverIndex)"
          :x2="centerX(hoverIndex)"
          :y1="marginTop"
          :y2="marginTop + innerHeight"
          stroke="var(--baseline)"
          stroke-width="1"
        />

        <template v-if="type === 'bar'">
          <g v-for="(s, si) in series" :key="s.name" :fill="SERIES_COLORS[si]">
            <template v-for="(value, i) in s.values" :key="i">
              <path v-if="value !== 0" :d="barPath(i, si, value)" />
            </template>
          </g>
          <template v-if="capLabels">
            <!-- No bar, no label: a row of zeros along the baseline is noise. -->
            <template v-for="(value, i) in series[0].values" :key="i">
              <text v-if="value !== 0" :x="centerX(i)" :y="y(Math.max(value, 0)) - 6" text-anchor="middle" class="cap-text">
                {{ formatValue(value, true) }}
              </text>
            </template>
          </template>
        </template>

        <template v-else>
          <g v-for="(s, si) in series" :key="s.name">
            <path :d="linePath(s.values)" fill="none" :stroke="SERIES_COLORS[si]" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <template v-for="(value, i) in s.values" :key="i">
              <circle
                v-if="showMarkers || hoverIndex === i"
                :cx="centerX(i)"
                :cy="y(value)"
                r="4"
                :fill="SERIES_COLORS[si]"
                stroke="var(--surface-1)"
                stroke-width="2"
              />
            </template>
          </g>
        </template>

        <template v-for="(label, i) in labels" :key="i">
          <text v-if="showLabel(i)" :x="centerX(i)" :y="HEIGHT - 6" text-anchor="middle" class="axis-text">{{ label }}</text>
        </template>

        <!-- Hit targets: the whole band, not the mark. -->
        <rect
          v-for="(_, i) in labels"
          :key="i"
          :x="MARGIN.left + band * i"
          :y="marginTop"
          :width="band"
          :height="innerHeight + MARGIN.bottom"
          fill="transparent"
          @mouseenter="hoverIndex = i"
        />
      </svg>

      <div
        v-if="hoverIndex !== null"
        class="pointer-events-none absolute top-0 z-10 min-w-28 rounded border border-neutral-200 bg-white px-2.5 py-1.5 text-xs shadow-md dark:border-neutral-700 dark:bg-neutral-800"
        :style="tooltipStyle"
      >
        <div class="font-medium text-[var(--text-primary)]">{{ labels[hoverIndex] }}</div>
        <div v-for="(s, si) in series" :key="s.name" class="mt-0.5 flex items-center justify-between gap-3">
          <span class="flex items-center gap-1.5 text-[var(--text-secondary)]">
            <span class="inline-block h-2 w-2 shrink-0 rounded-sm" :style="{ background: SERIES_COLORS[si] }" />
            {{ s.name }}
          </span>
          <span class="font-medium tabular-nums text-[var(--text-primary)]">{{ formatValue(s.values[hoverIndex]) }}</span>
        </div>
      </div>
    </div>

    <table class="sr-only">
      <caption>{{ title }}</caption>
      <thead>
        <tr>
          <th />
          <th v-for="s in series" :key="s.name">{{ s.name }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(label, i) in labels" :key="i">
          <th>{{ label }}</th>
          <td v-for="s in series" :key="s.name">{{ formatValue(s.values[i]) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* Surface values are the card backgrounds this renders on (white /
   neutral-900), so the marker ring disappears into the card. */
.viz-root {
  --surface-1: #ffffff;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --gridline: #e1e0d9;
  --baseline: #c3c2b7;
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-3: #1baf7a;
}
@media (prefers-color-scheme: dark) {
  .viz-root {
    --surface-1: #171717;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --gridline: #2c2c2a;
    --baseline: #383835;
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-3: #199e70;
  }
}
.axis-text {
  fill: var(--text-muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.cap-text {
  fill: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
}
</style>
