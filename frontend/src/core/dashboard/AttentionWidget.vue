<script setup lang="ts">
import { CheckCircleIcon, ChevronRightIcon, ExclamationCircleIcon, ExclamationTriangleIcon, InformationCircleIcon } from '@heroicons/vue/24/outline'
import { useI18n } from 'vue-i18n'

import { useFormat } from './format'
import type { AttentionData, Severity } from './types'

// Everything across the installed plugins that's waiting on someone. The
// backend only sends items with something to report, most severe first, so
// an empty list is a real "all clear".
defineProps<{ data: AttentionData }>()

const { t } = useI18n()
const format = useFormat()

// Severity is carried by icon shape and the sentence itself; the color
// only reinforces it.
const SEVERITY: Record<Severity, { icon: typeof CheckCircleIcon; tone: string }> = {
  critical: { icon: ExclamationCircleIcon, tone: 'text-red-600 dark:text-red-400' },
  warning: { icon: ExclamationTriangleIcon, tone: 'text-amber-600 dark:text-amber-400' },
  info: { icon: InformationCircleIcon, tone: 'text-blue-600 dark:text-blue-400' },
}
</script>

<template>
  <div v-if="data.items.length === 0" class="flex items-center gap-2 py-6 text-sm text-neutral-600 dark:text-neutral-400">
    <CheckCircleIcon class="h-5 w-5 text-green-600 dark:text-green-500" />
    {{ t('widgets.ui.allClear') }}
  </div>
  <ul v-else class="-mx-2 divide-y divide-neutral-100 dark:divide-neutral-800/60">
    <li v-for="item in data.items" :key="item.key">
      <component
        :is="item.route ? 'RouterLink' : 'div'"
        :to="item.route || undefined"
        class="flex items-center gap-3 rounded px-2 py-2.5 text-sm"
        :class="item.route ? 'hover:bg-neutral-50 dark:hover:bg-neutral-800/60' : ''"
      >
        <component :is="SEVERITY[item.severity].icon" class="h-5 w-5 shrink-0" :class="SEVERITY[item.severity].tone" />
        <span class="min-w-0 flex-1 text-neutral-800 dark:text-neutral-200">
          {{ t(`widgets.attentionItems.${item.key}`, { count: item.count }, item.count) }}
        </span>
        <span v-if="item.amount" class="shrink-0 font-medium tabular-nums text-neutral-900 dark:text-neutral-100">
          {{ format.money(Number(item.amount)) }}
        </span>
        <ChevronRightIcon v-if="item.route" class="h-4 w-4 shrink-0 text-neutral-400" />
      </component>
    </li>
  </ul>
</template>
