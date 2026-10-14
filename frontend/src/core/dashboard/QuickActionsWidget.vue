<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { plugins } from '@/plugins/registry'
import { useAuthStore } from '@/shared/stores/auth'
import { usePluginStore } from '@/shared/stores/plugins'

// One-click links to every page of every installed plugin -- built from the
// same manifests as the sidebar, so it never offers a page the tenant has
// removed (and gains a link the moment a plugin is added).
const { t } = useI18n()
const pluginStore = usePluginStore()

const auth = useAuthStore()

const pages = computed(() =>
  plugins
    .filter((plugin) => pluginStore.isActive(plugin.key))
    .flatMap((plugin) => plugin.pages)
    .filter((page) => auth.can(page.action)),
)
</script>

<template>
  <p v-if="pages.length === 0" class="py-8 text-center text-sm text-neutral-500">{{ t('widgets.ui.noPlugins') }}</p>
  <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-2">
    <RouterLink
      v-for="page in pages"
      :key="page.path"
      :to="page.path"
      class="flex items-center gap-2 rounded border border-neutral-200 px-3 py-2 text-sm text-neutral-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-neutral-800 dark:text-neutral-300 dark:hover:border-blue-800 dark:hover:bg-blue-950 dark:hover:text-blue-300"
    >
      <component :is="page.icon" class="h-4 w-4 shrink-0" />
      <span class="truncate">{{ t(page.labelKey) }}</span>
    </RouterLink>
  </div>
</template>
