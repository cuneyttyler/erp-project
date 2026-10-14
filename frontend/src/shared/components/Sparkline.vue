<script setup lang="ts">
import { computed } from 'vue'

// The trend strip on a stat tile: shape only, no axes -- the tile's
// headline is the current value and the delta names the comparison. Drawn
// in the de-emphasis gray with the latest point in the accent, so the eye
// lands on "now".
const props = defineProps<{ values: number[] }>()

const WIDTH = 96
const HEIGHT = 28
const PAD = 4

const points = computed(() => {
  const min = Math.min(...props.values)
  const max = Math.max(...props.values)
  const range = max - min
  return props.values.map((value, i) => ({
    x: props.values.length > 1 ? PAD + (i / (props.values.length - 1)) * (WIDTH - 2 * PAD) : WIDTH / 2,
    // A flat series sits on the midline rather than the floor.
    y: range === 0 ? HEIGHT / 2 : PAD + (1 - (value - min) / range) * (HEIGHT - 2 * PAD),
  }))
})
const path = computed(() => points.value.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' '))
const last = computed(() => points.value[points.value.length - 1])
</script>

<template>
  <svg v-if="values.length > 1" class="sparkline" :width="WIDTH" :height="HEIGHT" :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" aria-hidden="true">
    <path :d="path" fill="none" stroke="var(--trend)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
    <circle :cx="last.x" :cy="last.y" r="3" fill="var(--accent)" />
  </svg>
</template>

<style scoped>
.sparkline {
  --trend: #c3c2b7;
  --accent: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  .sparkline {
    --trend: #52514e;
    --accent: #3987e5;
  }
}
</style>
