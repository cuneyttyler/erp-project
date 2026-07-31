<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAIStore } from './store'

// The persistent AI side-panel (requirements.md REQ-CORE-AI-001) -- mounted
// once in App.vue, not per-page, so conversation state survives navigation
// between package modules.
const ai = useAIStore()
const { t } = useI18n()
const draft = ref('')

function submit() {
  if (!draft.value.trim()) return
  ai.sendMessage(draft.value)
  draft.value = ''
}
</script>

<template>
  <transition name="slide">
    <aside
      v-if="ai.isOpen"
      class="fixed right-0 top-0 z-40 flex h-full w-96 flex-col border-l border-neutral-200 bg-white shadow-lg dark:border-neutral-800 dark:bg-neutral-900"
    >
      <header
        class="flex items-center justify-between border-b border-neutral-200 px-4 py-3 dark:border-neutral-800"
      >
        <h2 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
          {{ t('aiPanel.title') }}
        </h2>
        <button
          class="text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100"
          aria-label="Close"
          @click="ai.toggle"
        >
          ✕
        </button>
      </header>

      <div class="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        <p v-if="ai.messages.length === 0" class="text-sm text-neutral-500">
          {{ t('aiPanel.empty') }}
        </p>
        <div
          v-for="message in ai.messages"
          :key="message.id"
          class="rounded-lg px-3 py-2 text-sm"
          :class="
            message.role === 'user'
              ? 'ml-8 bg-blue-600 text-white'
              : 'mr-8 bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100'
          "
        >
          <p>{{ message.text }}</p>
          <!-- REQ-CORE-AI-003: citations are first-class UI elements, not plain text -->
          <ul v-if="message.citations?.length" class="mt-2 space-y-1">
            <li v-for="c in message.citations" :key="c.route">
              <RouterLink :to="c.route" class="text-xs underline">{{ c.label }}</RouterLink>
            </li>
          </ul>
          <!-- REQ-AI-XCUT-003: a proposed action must look visibly different
               from something the AI already did -->
          <div
            v-if="message.pendingAction"
            class="mt-2 rounded border border-amber-400 bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200"
          >
            <p class="font-semibold">{{ t('aiPanel.confirmAction') }}</p>
            <p>{{ message.pendingAction.description }}</p>
          </div>
        </div>
      </div>

      <form class="flex gap-2 border-t border-neutral-200 p-3 dark:border-neutral-800" @submit.prevent="submit">
        <input
          v-model="draft"
          type="text"
          class="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-800"
          :placeholder="t('aiPanel.placeholder')"
        />
        <button
          type="submit"
          class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {{ t('aiPanel.send') }}
        </button>
      </form>
    </aside>
  </transition>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
