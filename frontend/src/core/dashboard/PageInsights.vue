<script setup lang="ts">
import { ChartBarIcon, ChevronDownIcon } from '@heroicons/vue/20/solid'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePluginStore } from '@/shared/stores/plugins'

import WidgetCard from './WidgetCard.vue'

// The charts at the top of a list page: the same widgets the panel shows
// (each loads its own data from plugins/widgets/<key>/data/), picked for
// what that page is about. A widget whose plugin is off, or that this user
// can't see, is simply left out. The strip can be folded away; that choice
// is remembered per page, in this browser only.
const props = withDefaults(
  defineProps<{
    // Which page this is (for remembering the folded state).
    screenKey: string
    widgets: string[]
    // The page's own records: when they change (something was created,
    // sent, received...) the charts reload, so the figures follow.
    follow?: unknown
  }>(),
  { follow: undefined },
)

const refreshToken = ref(0)
let pending: ReturnType<typeof setTimeout> | undefined
let first = true
watch(
  () => props.follow,
  () => {
    // The page's first load of its list isn't a change.
    if (first) {
      first = false
      return
    }
    clearTimeout(pending)
    pending = setTimeout(() => refreshToken.value++, 400)
  },
  { deep: true },
)

const { t } = useI18n()
const pluginStore = usePluginStore()

onMounted(() => {
  if (!pluginStore.isLoaded) pluginStore.load().catch(() => undefined)
})

const shown = computed(() =>
  props.widgets.map((key) => pluginStore.widgets.find((w) => w.key === key)).filter((w) => w !== undefined && w.is_available),
)

const storageKey = `insights-folded:${props.screenKey}`
function readFolded(): boolean {
  try {
    return localStorage.getItem(storageKey) === '1'
  } catch {
    return false
  }
}
const folded = ref(readFolded())
function toggle() {
  folded.value = !folded.value
  try {
    localStorage.setItem(storageKey, folded.value ? '1' : '0')
  } catch {
    // Storage unavailable (private window): the toggle still works for now.
  }
}

const gridClass = computed(() => {
  const n = shown.value.length
  if (n === 1) return 'grid-cols-1'
  if (n === 2) return 'grid-cols-1 lg:grid-cols-2'
  return 'grid-cols-1 lg:grid-cols-2 xl:grid-cols-3'
})
</script>

<template>
  <section v-if="shown.length" class="mt-4" :aria-label="t('widgets.ui.insights')">
    <button
      type="button"
      class="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
      :aria-expanded="!folded"
      @click="toggle"
    >
      <ChartBarIcon class="h-4 w-4" aria-hidden="true" />
      {{ t('widgets.ui.insights') }}
      <ChevronDownIcon class="h-4 w-4 transition-transform" :class="folded ? '-rotate-90' : ''" aria-hidden="true" />
    </button>
    <div v-if="!folded" class="mt-2 grid gap-4" :class="gridClass">
      <WidgetCard v-for="widget in shown" :key="widget!.key" :widget="widget!" :refresh-token="refreshToken" :linkable="false" />
    </div>
  </section>
</template>
