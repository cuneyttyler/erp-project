<script setup lang="ts">
import { computed, ref } from 'vue'

// A ranked list as horizontal bars -- the form for "top N by amount" where
// the category names are long (customers, vendors, accounts) and would
// collide under a vertical chart. One series, one color (bar length already
// carries the value; shading by rank would double-encode it), and every
// bar is direct-labeled, so no axis, legend or tooltip is needed.
const props = defineProps<{
  rows: { label: string; value: number }[]
  formatValue: (value: number) => string
}>()

const max = computed(() => Math.max(...props.rows.map((row) => row.value), 0) || 1)
const hoverIndex = ref<number | null>(null)

function widthPercent(value: number): string {
  // A non-zero value always shows at least a sliver of bar.
  return `${value > 0 ? Math.max((value / max.value) * 100, 1.5) : 0}%`
}
</script>

<template>
  <ol class="viz-root space-y-2.5" @mouseleave="hoverIndex = null">
    <li
      v-for="(row, i) in rows"
      :key="row.label"
      class="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto] items-center gap-3 text-sm transition-opacity"
      :class="hoverIndex !== null && hoverIndex !== i ? 'opacity-55' : ''"
      @mouseenter="hoverIndex = i"
    >
      <span class="truncate text-[var(--text-secondary)]" :title="row.label">{{ row.label }}</span>
      <span class="block h-2.5">
        <span class="block h-full rounded-r bg-[var(--series-1)]" :style="{ width: widthPercent(row.value) }" />
      </span>
      <span class="font-medium tabular-nums text-[var(--text-primary)]">{{ formatValue(row.value) }}</span>
    </li>
  </ol>
</template>

<style scoped>
.viz-root {
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --series-1: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  .viz-root {
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --series-1: #3987e5;
  }
}
</style>
