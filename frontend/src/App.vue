<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import AIPanel from '@/ai-panel/AIPanel.vue'
import { useAIStore } from '@/ai-panel/store'
import { setLocale } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'
import { useTenantStore } from '@/shared/stores/tenant'

// The persistent app shell (technical.md §10.1): nav + the always-mounted AI
// side-panel + the router-view where package modules render.
const ai = useAIStore()
const auth = useAuthStore()
const tenant = useTenantStore()
const router = useRouter()
const { t, locale } = useI18n()

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-full flex-col bg-white dark:bg-neutral-950">
    <header
      class="flex items-center justify-between border-b border-neutral-200 bg-white px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900"
    >
      <div class="flex items-center gap-6">
        <span class="font-semibold text-neutral-900 dark:text-neutral-100">{{ t('app.name') }}</span>
        <nav v-if="auth.isAuthenticated" class="flex flex-wrap gap-4 text-sm text-neutral-600 dark:text-neutral-400">
          <RouterLink to="/" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.dashboard') }}</RouterLink>
          <RouterLink to="/accounts" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.accounts') }}</RouterLink>
          <RouterLink to="/items" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.items') }}</RouterLink>
          <RouterLink to="/journal-entries" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.journalEntries') }}</RouterLink>
          <RouterLink to="/trial-balance" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.trialBalance') }}</RouterLink>
          <RouterLink to="/parties" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.parties') }}</RouterLink>
          <RouterLink to="/invoices" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.invoices') }}</RouterLink>
          <RouterLink to="/bills" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.bills') }}</RouterLink>
          <RouterLink to="/aging" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.aging') }}</RouterLink>
          <template v-if="tenant.hasPackage('inventory')">
            <RouterLink to="/warehouses" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.warehouses') }}</RouterLink>
            <RouterLink to="/stock-levels" class="hover:text-neutral-900 dark:hover:text-neutral-100">{{ t('nav.stockLevels') }}</RouterLink>
          </template>
          <RouterLink
            v-if="tenant.hasPackage('purchasing')"
            to="/purchase-orders"
            class="hover:text-neutral-900 dark:hover:text-neutral-100"
          >
            {{ t('nav.purchaseOrders') }}
          </RouterLink>
        </nav>
      </div>

      <div class="flex items-center gap-3">
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
      </div>
    </header>

    <main class="flex-1 overflow-y-auto bg-neutral-50 dark:bg-neutral-950">
      <RouterView />
    </main>

    <AIPanel v-if="auth.isAuthenticated" />
  </div>
</template>
