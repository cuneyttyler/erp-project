<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import AIPanel from '@/ai-panel/AIPanel.vue'
import { useAIStore } from '@/ai-panel/store'
import AppSidebar from '@/shared/components/AppSidebar.vue'
import { setLocale } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'
import { useEntityStore } from '@/shared/stores/entity'

// The persistent app shell (technical.md §10.1): a collapsible left sidebar
// (AppSidebar.vue) for navigation + a slim top bar for locale/entity/AI/
// logout + the always-mounted AI side-panel + the router-view where
// package modules render.
const ai = useAIStore()
const auth = useAuthStore()
const entity = useEntityStore()
const router = useRouter()
const { t, locale } = useI18n()

// REQ-CORE-ENT-001: load the tenant's entities once a session exists, so
// the header switcher (and every GL/AR/AP screen reading
// entity.currentEntityId) has real data before the user navigates anywhere.
watch(
  () => auth.isAuthenticated,
  (loggedIn) => {
    if (loggedIn) entity.fetchEntities()
  },
  { immediate: true },
)

const showNewEntityForm = ref(false)
const newEntityName = ref('')
const newEntityCode = ref('')

async function createEntity() {
  if (!newEntityName.value.trim() || !newEntityCode.value.trim()) return
  const created = await entity.createEntity({ name: newEntityName.value, code: newEntityCode.value })
  entity.setCurrentEntity(created.id)
  newEntityName.value = ''
  newEntityCode.value = ''
  showNewEntityForm.value = false
}

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
        <div v-if="auth.isAuthenticated && entity.entities.length > 0" class="relative flex items-center gap-1">
          <select
            class="rounded border border-neutral-300 bg-transparent px-2 py-1 text-sm dark:border-neutral-700"
            :value="entity.currentEntityId"
            @change="entity.setCurrentEntity(Number(($event.target as HTMLSelectElement).value))"
          >
            <option v-for="e in entity.entities" :key="e.id" :value="e.id">{{ e.code }} — {{ e.name }}</option>
          </select>
          <button
            class="rounded px-1.5 py-1 text-sm text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            title="Yeni şirket ekle"
            @click="showNewEntityForm = !showNewEntityForm"
          >
            +
          </button>
          <div
            v-if="showNewEntityForm"
            class="absolute right-0 top-full z-30 mt-1 w-56 space-y-1 rounded border border-neutral-200 bg-white p-2 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
          >
            <input
              v-model="newEntityName"
              placeholder="Şirket adı"
              class="w-full rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700 dark:bg-neutral-800"
            />
            <input
              v-model="newEntityCode"
              placeholder="Kod (ör. B)"
              class="w-full rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700 dark:bg-neutral-800"
            />
            <button
              class="w-full rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              @click="createEntity"
            >
              Oluştur
            </button>
          </div>
        </div>

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
