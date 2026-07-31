<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '@/shared/stores/auth'

// Placeholder home dashboard (REQ-CORE-RPT-001) -- role-specific KPI cards
// land here once there's enough Core data (GL, AR/AP) to summarize.
const { t } = useI18n()
const auth = useAuthStore()
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">
      {{ t('nav.dashboard') }}
    </h1>
    <p class="mt-2 text-sm text-neutral-500">
      {{ t('app.name') }} — logged in as {{ auth.user?.full_name || auth.user?.username }}.
    </p>

    <div class="mt-6 flex gap-3">
      <RouterLink
        to="/accounts"
        class="rounded border border-neutral-300 px-4 py-3 text-sm hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
      >
        {{ t('nav.accounts') }}
      </RouterLink>
      <RouterLink
        to="/journal-entries"
        class="rounded border border-neutral-300 px-4 py-3 text-sm hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
      >
        {{ t('nav.journalEntries') }}
      </RouterLink>
      <RouterLink
        to="/trial-balance"
        class="rounded border border-neutral-300 px-4 py-3 text-sm hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
      >
        {{ t('nav.trialBalance') }}
      </RouterLink>
    </div>
  </section>
</template>
