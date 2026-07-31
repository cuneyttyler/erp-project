<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import AIPanel from '@/ai-panel/AIPanel.vue'
import { useAIStore } from '@/ai-panel/store'
import AppSidebar from '@/shared/components/AppSidebar.vue'
import { setLocale } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'

// The persistent app shell (technical.md §10.1): a collapsible left sidebar
// (AppSidebar.vue) for navigation + a slim top bar for locale/AI/logout +
// the always-mounted AI side-panel + the router-view where package modules
// render.
const ai = useAIStore()
const auth = useAuthStore()
const router = useRouter()
const { t, locale } = useI18n()

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-full bg-white dark:bg-neutral-950">
    <AppSidebar v-if="auth.isAuthenticated" />

    <div class="flex flex-1 flex-col overflow-hidden">
      <header
        class="flex items-center justify-end gap-3 border-b border-neutral-200 bg-white px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900"
      >
        <select
          class="rounded border border-neutral-300 bg-transparent px-2 py-1 text-sm dark:border-neutral-700"
          :value="locale"
          @change="setLocale(($event.target as HTMLSelectElement).value as 'tr' | 'en')"
        >
          <option value="tr">TR</option>
          <option value="en">EN</option>
        </select>

        <button
          v-if="auth.isAuthenticated"
          class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          @click="ai.toggle"
        >
          {{ t('aiPanel.title') }}
        </button>

        <button
          v-if="auth.isAuthenticated"
          class="text-sm text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100"
          @click="logout"
        >
          {{ t('auth.logout') }}
        </button>
      </header>

      <main class="flex-1 overflow-y-auto bg-neutral-50 dark:bg-neutral-950">
        <RouterView />
      </main>
    </div>

    <AIPanel v-if="auth.isAuthenticated" />
  </div>
</template>
