<script setup lang="ts">
import { AdjustmentsHorizontalIcon, ArrowPathIcon } from '@heroicons/vue/24/outline'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import WidgetCard from '@/core/dashboard/WidgetCard.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useEntityStore } from '@/shared/stores/entity'
import { usePluginStore, type WidgetSize } from '@/shared/stores/plugins'

// The home panel (REQ-CORE-RPT-001). It has no content of its own: it lays
// out whichever widgets this user has switched on (Plugins > Panel
// widgets), in their order and at their sizes, and each widget only exists
// while the plugin behind it is installed. The panel itself is one of the
// two screens that can't be removed.
const { t, locale } = useI18n()
const auth = useAuthStore()
const entity = useEntityStore()
const plugins = usePluginStore()

// Finance widgets are scoped to the entity picked in the header. Wait for
// that selection before mounting any card, so each widget loads once with
// the right entity instead of twice.
const isReady = ref(false)
onMounted(async () => {
  if (entity.entities.length === 0) await entity.fetchEntities().catch(() => undefined)
  isReady.value = true
})

const refreshToken = ref(0)

// On a 12-column grid: four stat tiles to a row, charts and tables two to
// a row, a large widget the full width -- collapsing to fewer columns on
// narrower screens.
const SIZE_CLASS: Record<WidgetSize, string> = {
  sm: 'col-span-12 sm:col-span-6 xl:col-span-3',
  md: 'col-span-12 xl:col-span-6',
  lg: 'col-span-12',
}

const name = computed(() => auth.user?.full_name || auth.user?.username || '')
const today = computed(() =>
  new Intl.DateTimeFormat(locale.value === 'tr' ? 'tr-TR' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date()),
)
const entityName = computed(() => entity.entities.find((e) => e.id === entity.currentEntityId)?.name)
</script>

<template>
  <section class="p-6 lg:p-8">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('dashboard.welcome', { name }) }}</h1>
        <p class="mt-1 text-sm text-neutral-500">
          {{ today }}<template v-if="entityName"> · {{ entityName }}</template>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="flex items-center gap-1.5 rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800"
          @click="refreshToken++"
        >
          <ArrowPathIcon class="h-4 w-4" />
          {{ t('dashboard.refresh') }}
        </button>
        <RouterLink
          :to="{ name: 'plugins', query: { tab: 'widgets' } }"
          class="flex items-center gap-1.5 rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          <AdjustmentsHorizontalIcon class="h-4 w-4" />
          {{ t('dashboard.customize') }}
        </RouterLink>
      </div>
    </header>

    <div
      v-if="isReady && plugins.panelWidgets.length === 0"
      class="mt-8 rounded-lg border border-dashed border-neutral-300 p-10 text-center dark:border-neutral-700"
    >
      <p class="text-sm font-medium text-neutral-800 dark:text-neutral-200">{{ t('dashboard.emptyTitle') }}</p>
      <p class="mt-1 text-sm text-neutral-500">{{ t('dashboard.emptyBody') }}</p>
      <RouterLink
        :to="{ name: 'plugins', query: { tab: 'widgets' } }"
        class="mt-4 inline-block rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        {{ t('dashboard.addWidgets') }}
      </RouterLink>
    </div>

    <div v-else-if="isReady" class="mt-6 grid grid-cols-12 gap-4">
      <div v-for="widget in plugins.panelWidgets" :key="widget.key" :class="SIZE_CLASS[widget.size]">
        <WidgetCard :widget="widget" :refresh-token="refreshToken" />
      </div>
    </div>
  </section>
</template>
