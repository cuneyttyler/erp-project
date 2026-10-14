<script setup lang="ts">
import { ArrowRightIcon } from '@heroicons/vue/20/solid'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiClient } from '@/shared/api/client'
import { useEntityStore } from '@/shared/stores/entity'
import type { WidgetState } from '@/shared/stores/plugins'

import AttentionWidget from './AttentionWidget.vue'
import ChartWidget from './ChartWidget.vue'
import QuickActionsWidget from './QuickActionsWidget.vue'
import StatWidget from './StatWidget.vue'
import TableWidget from './TableWidget.vue'
import type { WidgetData } from './types'

// The frame around one panel widget: title, a link through to the page
// behind the figure, and the loading/error states. Each card loads its own
// data, so one slow or failing widget never holds up the rest of the panel.
const props = defineProps<{
  widget: WidgetState
  // Bumped by the panel's refresh button.
  refreshToken: number
}>()

const { t } = useI18n()
const entity = useEntityStore()

const data = ref<WidgetData | null>(null)
const isLoading = ref(false)
const hasError = ref(false)
let latestRequest = 0

async function load() {
  // Quick actions is rendered from the plugin manifests alone.
  if (props.widget.kind === 'quick_actions') {
    data.value = { kind: 'quick_actions' }
    return
  }
  const request = ++latestRequest
  isLoading.value = true
  hasError.value = false
  try {
    const response = await apiClient.get<WidgetData>(`plugins/widgets/${props.widget.key}/data/`, {
      params: entity.currentEntityId ? { entity: entity.currentEntityId } : {},
    })
    // The entity can change mid-flight; only the newest answer is shown.
    if (request === latestRequest) data.value = response.data
  } catch {
    if (request === latestRequest) hasError.value = true
  } finally {
    if (request === latestRequest) isLoading.value = false
  }
}

watch([() => entity.currentEntityId, () => props.refreshToken], load, { immediate: true })

const title = computed(() => t(`widgets.catalog.${props.widget.key}.title`))
const route = computed(() => (data.value && 'route' in data.value ? data.value.route : null))
</script>

<template>
  <article class="flex h-full flex-col rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <header class="mb-3 flex items-start justify-between gap-3">
      <h2 class="text-sm font-medium text-neutral-600 dark:text-neutral-400">{{ title }}</h2>
      <RouterLink
        v-if="route"
        :to="route"
        class="flex shrink-0 items-center gap-0.5 text-xs font-medium text-blue-700 hover:underline dark:text-blue-400"
        :aria-label="`${t('widgets.ui.view')}: ${title}`"
      >
        {{ t('widgets.ui.view') }}
        <ArrowRightIcon class="h-3.5 w-3.5" />
      </RouterLink>
    </header>

    <div v-if="hasError && !data" class="flex flex-1 flex-col items-start justify-center gap-2 py-4 text-sm text-neutral-500">
      {{ t('widgets.ui.loadFailed') }}
      <button class="rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800" @click="load">
        {{ t('widgets.ui.retry') }}
      </button>
    </div>

    <!-- First load: a quiet placeholder. On a refresh the previous figures
         stay in place, dimmed, so the panel doesn't jump. -->
    <div v-else-if="!data" class="flex-1 animate-pulse space-y-2 py-1" aria-busy="true">
      <div class="h-6 w-1/2 rounded bg-neutral-100 dark:bg-neutral-800" />
      <div class="h-3 w-3/4 rounded bg-neutral-100 dark:bg-neutral-800" />
    </div>

    <div v-else class="flex-1 transition-opacity" :class="isLoading ? 'opacity-50' : ''">
      <StatWidget v-if="data.kind === 'stat'" :data="data" />
      <ChartWidget v-else-if="data.kind === 'chart'" :data="data" :title="title" />
      <TableWidget v-else-if="data.kind === 'table'" :data="data" />
      <AttentionWidget v-else-if="data.kind === 'attention'" :data="data" />
      <QuickActionsWidget v-else-if="data.kind === 'quick_actions'" />
    </div>
  </article>
</template>
