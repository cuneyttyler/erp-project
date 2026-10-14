<script setup lang="ts">
import { ArrowDownIcon, ArrowUpIcon } from '@heroicons/vue/20/solid'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import Sparkline from '@/shared/components/Sparkline.vue'

import { useFormat } from './format'
import type { StatData } from './types'

// A stat tile: the headline figure, an optional signed change against a
// named period, a couple of supporting figures, and a trend strip. The
// change is colored by whether it's good news, not by its direction --
// expenses going up is red -- and always carries an arrow and the period
// it's compared to, so color is never the only signal.
const props = defineProps<{ data: StatData }>()

const { t } = useI18n()
const format = useFormat()

const headline = computed(() => format.value(Number(props.data.value), props.data.format))
const trend = computed(() => props.data.trend.map((point) => Number(point.value)))
// A trend with nothing in it is a flat line that says nothing; leave it out.
const hasTrend = computed(() => trend.value.some((value) => value !== 0))

const delta = computed(() => {
  if (!props.data.delta) return null
  const percent = Number(props.data.delta.percent)
  const isUp = percent > 0
  return {
    text: format.percent(percent),
    isUp,
    isFlat: percent === 0,
    isGood: isUp === (props.data.delta.good_when === 'up'),
    compare: t(`widgets.compare.${props.data.delta.compare_key}`),
  }
})
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- The figure is never truncated: on a narrow tile the trend strip
         wraps beneath it instead. -->
    <div class="flex flex-wrap items-end justify-between gap-x-3 gap-y-1">
      <span class="whitespace-nowrap text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{{ headline }}</span>
      <Sparkline v-if="hasTrend" :values="trend" class="shrink-0" />
    </div>

    <p v-if="delta" class="mt-1 flex items-center gap-1 text-xs">
      <span
        class="flex items-center gap-0.5 font-medium"
        :class="
          delta.isFlat
            ? 'text-neutral-500'
            : delta.isGood
              ? 'text-green-700 dark:text-green-500'
              : 'text-red-700 dark:text-red-400'
        "
      >
        <ArrowUpIcon v-if="delta.isUp" class="h-3.5 w-3.5" />
        <ArrowDownIcon v-else-if="!delta.isFlat" class="h-3.5 w-3.5" />
        {{ delta.text }}
      </span>
      <span class="text-neutral-500">{{ delta.compare }}</span>
    </p>

    <dl v-if="data.secondary.length" class="mt-auto space-y-1 pt-3 text-xs">
      <div v-for="line in data.secondary" :key="line.key" class="flex items-center justify-between gap-3">
        <dt class="truncate text-neutral-500">{{ t(`widgets.secondary.${line.key}`) }}</dt>
        <dd class="font-medium tabular-nums text-neutral-800 dark:text-neutral-200">{{ format.value(Number(line.value), line.format) }}</dd>
      </div>
    </dl>
  </div>
</template>
